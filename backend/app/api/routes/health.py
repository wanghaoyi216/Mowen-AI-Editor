"""Health check and system monitoring endpoints.

Exposes a family of `/api/v1/health/*` endpoints that complement the
top-level `/health` route defined in `app.main`:

* `GET /api/v1/health/detailed`   - per-dependency health probe
* `GET /api/v1/health/metrics`    - Prometheus-style exposition
* `GET /api/v1/health/rate-limit` - current NVIDIA rate limiter state
* `GET /api/v1/health/tasks`      - aggregate task/chapter counters
* `GET /api/v1/health/database`   - SQLAlchemy connection pool stats

Each probe is isolated with its own try/except block so a single
failing dependency never aborts the rest of the report.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.db.base import engine
from app.graph.client import build_neo4j_client
from app.models.ai_task import AITask
from app.models.chapter import Chapter
from app.services.rate_limiter import MAX_CALLS_PER_MINUTE, rate_limiter


logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


# ---------------------------------------------------------------------------
# In-process metrics registry
# ---------------------------------------------------------------------------
#
# Lightweight, dependency-free counters. Other modules can call
# ``metrics_registry.inc_llm_call(model)`` / ``observe_llm_latency`` to
# publish data that ``/api/v1/health/metrics`` will then expose in
# Prometheus text format. Missing keys simply render as 0.
#
# Histogram buckets are the standard Prometheus ``defbuckets`` for
# latency in seconds.

_HISTOGRAM_BUCKETS: tuple[float, ...] = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
)


class MetricsRegistry:
    """Thread-safe in-process metrics registry."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._task_status: Counter[str] = Counter()
        self._chapter_status: Counter[str] = Counter()
        self._llm_calls: Counter[str] = Counter()
        self._llm_latency_buckets: dict[str, dict[float, int]] = defaultdict(
            lambda: {bucket: 0 for bucket in _HISTOGRAM_BUCKETS}
        )
        self._llm_latency_sum: Counter[str] = Counter()
        self._llm_latency_count: Counter[str] = Counter()
        self._active_tasks: int = 0
        self._rate_limit_remaining: int | None = None

    # --- tasks -------------------------------------------------------------
    def inc_task(self, status: str) -> None:
        with self._lock:
            self._task_status[status] += 1

    def inc_chapter(self, status: str) -> None:
        with self._lock:
            self._chapter_status[status] += 1

    def set_active_tasks(self, value: int) -> None:
        with self._lock:
            self._active_tasks = max(0, int(value))

    # --- LLM ---------------------------------------------------------------
    def inc_llm_call(self, model: str) -> None:
        with self._lock:
            self._llm_calls[model] += 1

    def observe_llm_latency(self, model: str, latency_seconds: float) -> None:
        with self._lock:
            bucket_table = self._llm_latency_buckets[model]
            for boundary in _HISTOGRAM_BUCKETS:
                if latency_seconds <= boundary:
                    bucket_table[boundary] += 1
            self._llm_latency_sum[model] += latency_seconds
            self._llm_latency_count[model] += 1

    def set_rate_limit_remaining(self, value: int) -> None:
        with self._lock:
            self._rate_limit_remaining = max(0, int(value))

    # --- snapshot helpers --------------------------------------------------
    def task_status_snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._task_status)

    def chapter_status_snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._chapter_status)

    def llm_calls_snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._llm_calls)

    def llm_latency_snapshot(self) -> dict[str, dict[str, float]]:
        with self._lock:
            models = set(self._llm_latency_buckets) | set(self._llm_latency_sum) | set(self._llm_latency_count)
            return {
                model: {
                    "buckets": {b: self._llm_latency_buckets[model].get(b, 0) for b in _HISTOGRAM_BUCKETS},
                    "sum": float(self._llm_latency_sum[model]),
                    "count": int(self._llm_latency_count[model]),
                }
                for model in models
            }

    def active_tasks(self) -> int:
        with self._lock:
            return self._active_tasks

    def rate_limit_remaining(self) -> int | None:
        with self._lock:
            return self._rate_limit_remaining


metrics_registry = MetricsRegistry()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _format_float(value: float) -> str:
    """Render a float in Prometheus-friendly form (no scientific notation)."""
    if value != value:  # NaN
        return "NaN"
    if value == float("inf"):
        return "+Inf"
    if value == float("-inf"):
        return "-Inf"
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def _current_window_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return (window_start, window_end) for the per-minute rate-limit window."""
    current = (now or _now()).astimezone(timezone.utc)
    start = current.replace(second=0, microsecond=0)
    end = start + timedelta(minutes=1)
    return start, end


# ---------------------------------------------------------------------------
# /detailed
# ---------------------------------------------------------------------------
def _probe_postgres(db: Session | None) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        if db is None:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        else:
            db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        return {"ok": True, "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001 - we want every error captured
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        logger.warning("Postgres health probe failed: %s", exc, exc_info=False)
        return {"ok": False, "latency_ms": latency_ms, "error": str(exc)[:200]}


def _probe_neo4j() -> dict[str, Any]:
    started = time.perf_counter()
    client: Any | None = None
    try:
        client = build_neo4j_client()
        with client._driver.session(database=client._database) as session:
            session.run("RETURN 1 AS ok").consume()
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        return {"ok": True, "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        logger.warning("Neo4j health probe failed: %s", exc, exc_info=False)
        return {"ok": False, "latency_ms": latency_ms, "error": str(exc)[:200]}
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass


def _probe_redis() -> dict[str, Any]:
    started = time.perf_counter()
    try:
        client = get_redis_client()
        pong = client.ping()
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        return {"ok": bool(pong), "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        logger.warning("Redis health probe failed: %s", exc, exc_info=False)
        return {"ok": False, "latency_ms": latency_ms, "error": str(exc)[:200]}


@router.get("/detailed")
def detailed_health(db: Session = Depends(get_db_session)) -> dict[str, Any]:
    """Per-dependency health probe. Failures in one service do not skip the others."""
    services: dict[str, dict[str, Any]] = {}
    services["postgres"] = _probe_postgres(db)
    services["neo4j"] = _probe_neo4j()
    services["redis"] = _probe_redis()

    ok_count = sum(1 for value in services.values() if value.get("ok"))
    if ok_count == len(services):
        status = "healthy"
    elif ok_count == 0:
        status = "unhealthy"
    else:
        status = "degraded"

    return {
        "status": status,
        "services": services,
        "timestamp": _now().isoformat(),
        "version": settings.app_version,
    }


# ---------------------------------------------------------------------------
# /metrics
# ---------------------------------------------------------------------------
@router.get("/metrics")
def prometheus_metrics(db: Session = Depends(get_db_session)) -> Response:
    """Render in-process counters in Prometheus text exposition format."""
    lines: list[str] = []
    task_counts = metrics_registry.task_status_snapshot()
    if task_counts:
        lines.append("# HELP novel_ai_tasks_total Total AI tasks by status.")
        lines.append("# TYPE novel_ai_tasks_total counter")
        for status, count in sorted(task_counts.items()):
            lines.append(f'novel_ai_tasks_total{{status="{status}"}} {count}')
    else:
        lines.append("# HELP novel_ai_tasks_total Total AI tasks by status.")
        lines.append("# TYPE novel_ai_tasks_total counter")
        lines.append("novel_ai_tasks_total 0")

    chapter_counts = metrics_registry.chapter_status_snapshot()
    lines.append("# HELP novel_ai_chapters_total Total chapters by status.")
    lines.append("# TYPE novel_ai_chapters_total counter")
    if chapter_counts:
        for status, count in sorted(chapter_counts.items()):
            lines.append(f'novel_ai_chapters_total{{status="{status}"}} {count}')
    else:
        lines.append("novel_ai_chapters_total 0")

    llm_calls = metrics_registry.llm_calls_snapshot()
    lines.append("# HELP novel_ai_llm_calls_total Total LLM calls by model.")
    lines.append("# TYPE novel_ai_llm_calls_total counter")
    if llm_calls:
        for model, count in sorted(llm_calls.items()):
            lines.append(f'novel_ai_llm_calls_total{{model="{model}"}} {count}')
    else:
        lines.append("novel_ai_llm_calls_total 0")

    latency_snapshot = metrics_registry.llm_latency_snapshot()
    lines.append("# HELP novel_ai_llm_latency_seconds LLM call latency histogram.")
    lines.append("# TYPE novel_ai_llm_latency_seconds histogram")
    if latency_snapshot:
        for model, data in sorted(latency_snapshot.items()):
            cumulative = 0
            for boundary in _HISTOGRAM_BUCKETS:
                cumulative = data["buckets"].get(boundary, 0)
                lines.append(
                    f'novel_ai_llm_latency_seconds_bucket{{model="{model}",le="{_format_float(boundary)}"}} {cumulative}'
                )
            count = data["count"]
            lines.append(f'novel_ai_llm_latency_seconds_bucket{{model="{model}",le="+Inf"}} {count}')
            lines.append(f'novel_ai_llm_latency_seconds_sum{{model="{model}"}} {_format_float(data["sum"])}')
            lines.append(f'novel_ai_llm_latency_seconds_count{{model="{model}"}} {count}')
    else:
        lines.append("novel_ai_llm_latency_seconds_bucket{le=\"+Inf\"} 0")
        lines.append("novel_ai_llm_latency_seconds_sum 0")
        lines.append("novel_ai_llm_latency_seconds_count 0")

    remaining = metrics_registry.rate_limit_remaining()
    if remaining is None:
        try:
            remaining = rate_limiter.get_remaining()
            metrics_registry.set_rate_limit_remaining(remaining)
        except Exception:  # noqa: BLE001
            remaining = 0
    lines.append("# HELP novel_ai_rate_limit_remaining NVIDIA API calls remaining in the current minute window.")
    lines.append("# TYPE novel_ai_rate_limit_remaining gauge")
    lines.append(f"novel_ai_rate_limit_remaining {remaining}")

    active = metrics_registry.active_tasks()
    try:
        active = int(
            db.execute(select(func.count(AITask.id)).where(AITask.status == "running")).scalar() or 0
        )
        metrics_registry.set_active_tasks(active)
    except Exception:  # noqa: BLE001
        pass
    lines.append("# HELP novel_ai_active_tasks Number of AI tasks currently in running state.")
    lines.append("# TYPE novel_ai_active_tasks gauge")
    lines.append(f"novel_ai_active_tasks {active}")

    body = "\n".join(lines) + "\n"
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")


# ---------------------------------------------------------------------------
# /rate-limit
# ---------------------------------------------------------------------------
@router.get("/rate-limit")
def rate_limit_status() -> dict[str, Any]:
    """Current NVIDIA per-minute rate limiter snapshot."""
    try:
        remaining = rate_limiter.get_remaining()
        metrics_registry.set_rate_limit_remaining(remaining)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read rate limiter: %s", exc)
        remaining = 0

    window_start, window_end = _current_window_bounds()
    return {
        "max_calls_per_window": MAX_CALLS_PER_MINUTE,
        "remaining": remaining,
        "current_window_start": window_start.isoformat(),
        "current_window_end": window_end.isoformat(),
        "next_window_start": window_end.isoformat(),
        "now": _now().isoformat(),
    }


# ---------------------------------------------------------------------------
# /tasks
# ---------------------------------------------------------------------------
@router.get("/tasks")
def task_statistics(db: Session = Depends(get_db_session)) -> dict[str, Any]:
    """Aggregate counters for tasks and chapters. Best-effort, isolated failures."""
    payload: dict[str, Any] = {
        "tasks_total": 0,
        "tasks_by_status": {"running": 0, "completed": 0, "failed": 0, "paused": 0, "other": 0},
        "avg_task_duration_seconds": 0.0,
        "total_chapters_generated": 0,
    }

    try:
        rows = db.execute(
            select(AITask.status, func.count(AITask.id)).group_by(AITask.status)
        ).all()
        status_counts = {str(status): int(count) for status, count in rows}
        by_status = payload["tasks_by_status"]
        total = 0
        for status, count in status_counts.items():
            total += count
            if status in by_status:
                by_status[status] = count
            else:
                by_status["other"] += count
        payload["tasks_total"] = total
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to aggregate task status counts: %s", exc)

    try:
        avg_row = db.execute(
            select(
                func.avg(
                    func.extract(
                        "epoch",
                        AITask.finished_at - AITask.started_at,
                    )
                )
            ).where(AITask.started_at.is_not(None), AITask.finished_at.is_not(None))
        ).scalar()
        if avg_row is not None:
            payload["avg_task_duration_seconds"] = round(float(avg_row), 3)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to compute avg task duration: %s", exc)

    try:
        chapter_total = db.execute(
            select(func.count(Chapter.id)).where(Chapter.final_content.is_not(None))
        ).scalar()
        payload["total_chapters_generated"] = int(chapter_total or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to count generated chapters: %s", exc)

    # Mirror totals into the metrics registry so /metrics reflects them.
    for status, count in payload["tasks_by_status"].items():
        if count:
            metrics_registry.inc_task(status)
    if payload["total_chapters_generated"]:
        metrics_registry.inc_chapter("generated")
    metrics_registry.set_active_tasks(payload["tasks_by_status"].get("running", 0))

    return payload


# ---------------------------------------------------------------------------
# /database
# ---------------------------------------------------------------------------
@router.get("/database")
def database_pool_status(db: Session = Depends(get_db_session)) -> dict[str, Any]:
    """SQLAlchemy connection pool stats plus a fresh connectivity probe."""
    pool_info: dict[str, Any] = {}
    try:
        pool = engine.pool
        pool_info = {
            "size": getattr(pool, "size", lambda: None)(),
            "checked_in": getattr(pool, "checkedin", lambda: None)(),
            "checked_out": getattr(pool, "checkedout", lambda: None)(),
            "overflow": getattr(pool, "overflow", lambda: None)(),
            "max_overflow": getattr(pool, "_max_overflow", None),
            "timeout": getattr(pool, "_timeout", None),
            "recycle": getattr(pool, _recycle_attr(pool), None),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read SQLAlchemy pool stats: %s", exc)
        pool_info = {"error": str(exc)[:200]}

    started = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        probe = {"ok": True, "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        logger.warning("Database probe failed: %s", exc)
        probe = {"ok": False, "latency_ms": latency_ms, "error": str(exc)[:200]}

    return {
        "url": _redact_url(settings.database_url),
        "pool": pool_info,
        "probe": probe,
        "timestamp": _now().isoformat(),
    }


def _recycle_attr(pool: Any) -> str:
    """Return the pool attribute name holding the recycle setting, if any."""
    for candidate in ("_recycle", "_pool_recycle", "recycle"):
        if hasattr(pool, candidate):
            return candidate
    return "_recycle"


def _redact_url(url: str) -> str:
    """Strip the password component from a SQLAlchemy URL."""
    try:
        if "@" in url and "://" in url:
            scheme, rest = url.split("://", 1)
            if "@" in rest:
                creds, host = rest.split("@", 1)
                if ":" in creds:
                    user, _ = creds.split(":", 1)
                    return f"{scheme}://{user}:***@{host}"
        return url
    except Exception:  # noqa: BLE001
        return "***"
