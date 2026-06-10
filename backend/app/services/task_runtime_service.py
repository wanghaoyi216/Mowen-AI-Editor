import json
import logging
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.db.base import SessionLocal
from app.models.ai_task import AITask, TaskStep
from app.schemas.task_runtime import (
    TaskControlRequest,
    TaskRuntimeState,
    TaskStatusUpdate,
    TaskStepRuntimeState,
    TaskStepStatusUpdate,
)


logger = logging.getLogger(__name__)
TERMINAL_STATUSES = {"completed", "failed", "stopped"}


def _task_key(project_id: int, task_id: int) -> str:
    return f"novel-ai-editor:project:{project_id}:task:{task_id}:runtime"


def _task_steps_key(project_id: int, task_id: int) -> str:
    return f"novel-ai-editor:project:{project_id}:task:{task_id}:steps"


def _task_tool_errors_key(project_id: int, task_id: int) -> str:
    return f"novel-ai-editor:project:{project_id}:task:{task_id}:tool_errors"


@contextmanager
def _session_scope(db: Session | None = None):
    if db is not None:
        yield db, False
        return
    session = SessionLocal()
    try:
        yield session, True
    finally:
        session.close()


def _commit_if_owned(db: Session, owned: bool) -> None:
    if owned:
        db.commit()


def _call_get_task_runtime_state(project_id: int, task_id: int, db: Session | None = None) -> TaskRuntimeState | None:
    try:
        return get_task_runtime_state(project_id, task_id, db)
    except TypeError:
        return get_task_runtime_state(project_id, task_id)


def _call_get_task_step_runtime_states(
    project_id: int,
    task_id: int,
    db: Session | None = None,
) -> list[TaskStepRuntimeState]:
    try:
        return get_task_step_runtime_states(project_id, task_id, db)
    except TypeError:
        return get_task_step_runtime_states(project_id, task_id)


def _call_set_task_runtime_state(
    project_id: int,
    task_id: int,
    payload: TaskStatusUpdate,
    db: Session | None = None,
) -> TaskRuntimeState:
    try:
        return set_task_runtime_state(project_id, task_id, payload, db=db)
    except TypeError:
        return set_task_runtime_state(project_id, task_id, payload)


def _call_set_task_step_runtime_state(
    project_id: int,
    task_id: int,
    payload: TaskStepStatusUpdate,
    db: Session | None = None,
) -> TaskStepRuntimeState:
    try:
        return set_task_step_runtime_state(project_id, task_id, payload, db=db)
    except TypeError:
        return set_task_step_runtime_state(project_id, task_id, payload)


def _persist_task_runtime_state(db: Session, task_id: int, payload: TaskStatusUpdate) -> None:
    task = db.get(AITask, task_id)
    if task is None:
        return
    task.status = payload.status
    if payload.status == "running" and task.started_at is None:
        task.started_at = datetime.now(UTC)
    if payload.status in TERMINAL_STATUSES:
        task.finished_at = datetime.now(UTC)
    if payload.status == "failed":
        task.error_message = payload.message
    if payload.message:
        previous_trace = task.reasoning_trace or ""
        trace_line = f"[{payload.status}] {payload.current_step or 'runtime'}: {payload.message}"
        if trace_line not in previous_trace:
            task.reasoning_trace = (previous_trace + "\n" + trace_line).strip()
    db.add(task)


def _persist_task_step_runtime_state(db: Session, task_id: int, payload: TaskStepStatusUpdate) -> None:
    step = db.scalar(
        select(TaskStep)
        .where(TaskStep.task_id == task_id, TaskStep.step_no == payload.step_no)
        .order_by(TaskStep.id.desc())
        .limit(1)
    )
    if step is None:
        return
    step.status = payload.status
    step.react_state = payload.react_state
    if payload.status == "running" and step.started_at is None:
        step.started_at = datetime.now(UTC)
    if payload.status in TERMINAL_STATUSES:
        step.finished_at = datetime.now(UTC)
    if payload.status == "failed":
        step.error_message = payload.message
    elif payload.message:
        step.output_payload = payload.message
    db.add(step)


def _write_redis_safely(operation: Callable[[], None]) -> None:
    try:
        operation()
    except Exception as exc:
        logger.warning("Redis runtime cache write skipped: %s", exc)


def _read_redis_safely(operation: Callable[[], object]) -> object | None:
    try:
        return operation()
    except Exception as exc:
        logger.warning("Redis runtime cache read skipped: %s", exc)
        return None


def set_task_runtime_state(
    project_id: int,
    task_id: int,
    payload: TaskStatusUpdate,
    db: Session | None = None,
) -> TaskRuntimeState:
    state = TaskRuntimeState(
        task_id=task_id,
        project_id=project_id,
        status=payload.status,
        current_step=payload.current_step,
        message=payload.message,
    )
    with _session_scope(db) as (session, owned):
        _persist_task_runtime_state(session, task_id, payload)
        _commit_if_owned(session, owned)

    def cache() -> None:
        client = get_redis_client()
        client.setex(
            _task_key(project_id, task_id),
            settings.task_runtime_cache_ttl_seconds,
            state.model_dump_json(),
        )

    _write_redis_safely(cache)
    return state


def get_task_runtime_state(project_id: int, task_id: int, db: Session | None = None) -> TaskRuntimeState | None:
    raw = _read_redis_safely(lambda: get_redis_client().get(_task_key(project_id, task_id)))
    if raw is None:
        with _session_scope(db) as (session, _owned):
            return rebuild_task_runtime_state(session, project_id, task_id)
    return TaskRuntimeState.model_validate(json.loads(raw))


def control_task_runtime_state(
    project_id: int,
    task_id: int,
    payload: TaskControlRequest,
    db: Session | None = None,
) -> TaskRuntimeState:
    current = _call_get_task_runtime_state(project_id, task_id, db)
    action = payload.action.lower()
    if action == "pause":
        status = "paused"
        current_step = current.current_step if current else "paused"
        message = payload.message or "Task paused by human supervisor"
    elif action == "resume":
        status = "running"
        current_step = current.current_step if current else "resumed"
        message = payload.message or "Task resumed by human supervisor"
    elif action == "stop":
        status = "stopped"
        current_step = "stopped"
        message = payload.message or "Task stopped by human supervisor"
    else:
        raise ValueError("Unsupported task control action")
    return _call_set_task_runtime_state(
        project_id,
        task_id,
        TaskStatusUpdate(status=status, current_step=current_step, message=message),
        db=db,
    )


def set_task_step_runtime_state(
    project_id: int,
    task_id: int,
    payload: TaskStepStatusUpdate,
    db: Session | None = None,
) -> TaskStepRuntimeState:
    state = TaskStepRuntimeState(
        task_id=task_id,
        project_id=project_id,
        step_no=payload.step_no,
        step_name=payload.step_name,
        status=payload.status,
        react_state=payload.react_state,
        message=payload.message,
    )
    with _session_scope(db) as (session, owned):
        _persist_task_step_runtime_state(session, task_id, payload)
        _commit_if_owned(session, owned)

    def cache() -> None:
        client = get_redis_client()
        key = _task_steps_key(project_id, task_id)
        client.hset(key, str(payload.step_no), state.model_dump_json())
        client.expire(key, settings.task_runtime_cache_ttl_seconds)

    _write_redis_safely(cache)
    return state


def get_task_step_runtime_states(
    project_id: int,
    task_id: int,
    db: Session | None = None,
) -> list[TaskStepRuntimeState]:
    raw_map = _read_redis_safely(lambda: get_redis_client().hgetall(_task_steps_key(project_id, task_id)))
    if not raw_map:
        with _session_scope(db) as (session, _owned):
            return rebuild_task_step_runtime_states(session, project_id, task_id)
    items = [TaskStepRuntimeState.model_validate(json.loads(item)) for item in raw_map.values()]
    return sorted(items, key=lambda item: item.step_no)


def rebuild_task_runtime_state(db: Session, project_id: int, task_id: int) -> TaskRuntimeState | None:
    task = db.get(AITask, task_id)
    if task is None or task.project_id != project_id:
        return None
    latest_step = db.scalar(
        select(TaskStep)
        .where(TaskStep.task_id == task_id)
        .order_by(TaskStep.step_no.desc(), TaskStep.id.desc())
        .limit(1)
    )
    current_step = latest_step.step_name if latest_step is not None else task.status
    message = "Runtime state rebuilt from database after Redis miss"
    return _call_set_task_runtime_state(
        project_id,
        task_id,
        TaskStatusUpdate(status=task.status, current_step=current_step, message=message),
        db=db,
    )


def get_or_rebuild_task_runtime_state(db: Session, project_id: int, task_id: int) -> TaskRuntimeState | None:
    state = _call_get_task_runtime_state(project_id, task_id, db)
    if state is not None:
        return state
    return rebuild_task_runtime_state(db, project_id, task_id)


def rebuild_task_step_runtime_states(db: Session, project_id: int, task_id: int) -> list[TaskStepRuntimeState]:
    task = db.get(AITask, task_id)
    if task is None or task.project_id != project_id:
        return []
    steps = list(db.scalars(select(TaskStep).where(TaskStep.task_id == task_id).order_by(TaskStep.step_no.asc())))
    states: list[TaskStepRuntimeState] = []
    for step in steps:
        states.append(
            _call_set_task_step_runtime_state(
                project_id,
                task_id,
                TaskStepStatusUpdate(
                    step_no=step.step_no,
                    step_name=step.step_name,
                    status=step.status,
                    react_state=step.react_state,
                    message="Step runtime state rebuilt from database after Redis miss",
                ),
                db=db,
            )
        )
    return states


def get_or_rebuild_task_step_runtime_states(db: Session, project_id: int, task_id: int) -> list[TaskStepRuntimeState]:
    states = _call_get_task_step_runtime_states(project_id, task_id, db)
    if states:
        return states
    return rebuild_task_step_runtime_states(db, project_id, task_id)


# ---------------------------------------------------------------------------
# Tool 错误累计（B2 任务）
# ---------------------------------------------------------------------------

def record_tool_error(
    project_id: int,
    task_id: int,
    tool: str,
    error_code: str,
    remediation: str,
    phase: str = "",
    severity: str = "warning",
) -> list[dict]:
    """Append a tool error entry to the task's runtime tool_errors list.

    用于 B2 任务：编排链在工具返回 ``error_code``（如 ``MISSING_TAVILY_KEY``）
    时调用本函数累计错误。错误列表存放在 Redis 独立 key
    （``...:task:<task_id>:tool_errors``），TTL 与 runtime 一致；
    Redis 不可用时降级为 best-effort（不阻断主流程）。

    返回写入后的当前错误列表，便于调用方做调试或断言。
    """
    if not task_id:
        return []
    entry = {
        "tool": str(tool or ""),
        "error_code": str(error_code or ""),
        "remediation": str(remediation or ""),
        "phase": str(phase or ""),
        "severity": str(severity or "warning"),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    key = _task_tool_errors_key(project_id, task_id)

    def _append() -> list[dict]:
        client = get_redis_client()
        try:
            raw = client.get(key)
        except Exception:
            raw = None
        items: list[dict] = []
        if raw:
            try:
                loaded = json.loads(raw)
                if isinstance(loaded, list):
                    items = [x for x in loaded if isinstance(x, dict)]
            except Exception:
                items = []
        items.append(entry)
        try:
            client.setex(
                key,
                settings.task_runtime_cache_ttl_seconds,
                json.dumps(items, ensure_ascii=False),
            )
        except Exception:
            pass
        return items

    written = _read_redis_safely(lambda: _append())
    if not isinstance(written, list):
        return [entry]
    return written


def get_task_tool_errors(project_id: int, task_id: int) -> list[dict]:
    """读取任务的累积 tool_errors 列表。Redis miss 时返回空列表。"""
    if not task_id:
        return []
    key = _task_tool_errors_key(project_id, task_id)

    def _read() -> object:
        client = get_redis_client()
        return client.get(key)

    raw = _read_redis_safely(_read)
    if not raw:
        return []
    try:
        loaded = json.loads(raw)
    except Exception:
        return []
    if not isinstance(loaded, list):
        return []
    return [x for x in loaded if isinstance(x, dict)]


def clear_task_tool_errors(project_id: int, task_id: int) -> None:
    """清空任务的 tool_errors 列表（重置 / 调试用）。"""
    if not task_id:
        return
    key = _task_tool_errors_key(project_id, task_id)

    def _clear() -> None:
        client = get_redis_client()
        client.delete(key)

    _write_redis_safely(_clear)
