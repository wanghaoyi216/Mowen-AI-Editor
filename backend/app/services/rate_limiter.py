"""100% in-process 线程安全的 token bucket 限流器（已弃用 Redis）。

设计说明：
- v2-overhaul 中间件重构：删除 Redis，本限流器仅依赖本地内存字典 + threading.Lock。
- 单进程内多线程（包括 asyncto thread pool）共享同一份计数。
- 重启进程 / 多实例部署会丢失计数（这是取舍，不依赖外部中间件）。
- LLM 调用统计 STATS 仍是模块级共享，配合 _STATS_LOCK 保证线程安全。
"""

import logging
import threading
import time
from datetime import datetime, timezone

from app.core.config import settings


logger = logging.getLogger(__name__)

MAX_CALLS_PER_MINUTE = 40
_MAX_BACKOFF = 60

# ---------------------------------------------------------------------------
# 模块级 LLM 调用统计（Task 6）
# ---------------------------------------------------------------------------
STATS: dict = {
    "total_calls": 0,
    "total_tokens": 0,
    "total_latency_ms": 0,
    "failure_count": 0,
    "by_model": {},
}
_STATS_LOCK = threading.Lock()

# 100% in-process token bucket：key = "YYYYMMDDHHMM"，value = 当前分钟内已用 token 数
_BUCKET: dict[str, int] = {}
_BUCKET_LOCK = threading.Lock()


class NVIDIARateLimiter:
    """Token bucket 限流器，v2 起 100% in-process，不再依赖 Redis。

    旧实现使用 Redis INCR + EXPIRE 做原子计数；新实现使用本地字典 +
    threading.Lock 做原子计数（足以支撑单进程部署）。
    """

    def __init__(self, max_calls: int | None = None) -> None:
        self._max_calls = max_calls if max_calls is not None else settings.rate_limit_calls_per_minute

    @property
    def _current_key(self) -> str:
        now = datetime.now(timezone.utc)
        return f"rate_limit:nvidia:{now.strftime('%Y%m%d%H%M')}"

    def _increment(self) -> int:
        """原子地递增当前分钟窗口计数并返回新值。"""
        key = self._current_key
        with _BUCKET_LOCK:
            count = _BUCKET.get(key, 0) + 1
            _BUCKET[key] = count
            # 简单清理：超过 5 分钟的旧 key 顺手删除，避免字典无限增长
            if len(_BUCKET) > 128:
                self._cleanup_expired()
            return count

    def _decrement(self) -> int:
        """原子地递减当前分钟窗口计数（>= 0），返回新值。失败/重试场景下释放 token 用。"""
        key = self._current_key
        with _BUCKET_LOCK:
            count = _BUCKET.get(key, 0) - 1
            count = max(0, count)
            _BUCKET[key] = count
            return count

    @staticmethod
    def _cleanup_expired() -> None:
        """清理超过 2 分钟的旧 key（仅在持有 _BUCKET_LOCK 时调用）。"""
        current = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        # 简单实现：只保留等于当前分钟的 key
        stale = [k for k in list(_BUCKET.keys()) if not k.endswith(current)]
        for k in stale:
            _BUCKET.pop(k, None)

    def acquire(self) -> bool:
        """阻塞直到获得 token，然后消耗一个 token。

        触发限流时使用指数退避（最大 60 秒）。
        """
        backoff = 1.0
        attempt = 0

        while True:
            current_count = self._increment()

            if current_count <= self._max_calls:
                if attempt > 0:
                    logger.info(
                        "NVIDIA rate limiter: token acquired after %d retries",
                        attempt,
                    )
                # 统计：每次成功获取 token 累加 total_calls
                with _STATS_LOCK:
                    STATS["total_calls"] += 1
                return True

            # 触发限流：超额的 increment 需要回退，否则会持续扣 token
            self._decrement()

            # 触发限流，按指数退避等待
            logger.warning(
                "NVIDIA API rate limit reached (%d/%d), "
                "waiting %.1fs before retry (attempt %d)",
                current_count,
                self._max_calls,
                backoff,
                attempt + 1,
            )

            time.sleep(backoff)
            attempt += 1
            backoff = min(backoff * 2, _MAX_BACKOFF)

    def try_acquire(self) -> bool:
        """非阻塞获取 token。满了直接返回 False（不抛错、不等待）。

        用于短路探针：探测主模型时如果 token 已耗尽，直接切 fallback。
        """
        current_count = self._increment()
        if current_count <= self._max_calls:
            with _STATS_LOCK:
                STATS["total_calls"] += 1
            return True
        # 超额：回退
        self._decrement()
        return False

    def release(self) -> None:
        """释放一个已获取的 token（调用失败/短路切走时使用）。

        不会回退 STATS.total_calls，避免重复计数。
        """
        self._decrement()
        logger.debug("NVIDIA rate limiter: token released (current minute)")

    def get_remaining(self) -> int:
        """返回当前分钟窗口内剩余可调用次数。"""
        try:
            key = self._current_key
            with _BUCKET_LOCK:
                current_count = _BUCKET.get(key, 0)
            remaining = self._max_calls - current_count
            return max(0, remaining)
        except Exception as exc:
            logger.warning("Rate limiter get_remaining error: %s", exc)
            return 0

    def reset(self) -> None:
        """重置当前窗口计数器（仅供测试使用）。"""
        try:
            key = self._current_key
            with _BUCKET_LOCK:
                _BUCKET.pop(key, None)
            logger.info("NVIDIA rate limiter: reset counter for key %s", key)
        except Exception as exc:
            logger.error("Rate limiter reset error: %s", exc)

    # ------------------------------------------------------------------
    # LLM 调用统计（Task 6）
    # ------------------------------------------------------------------
    def record_call(
        self,
        model_id: str,
        tokens: int,
        latency_ms: int,
        success: bool = True,
    ) -> None:
        """记录单次 LLM 调用。

        Args:
            model_id: 模型标识（如 "nvidia/llama-3.1-nemotron-70b-instruct"）
            tokens: 本次调用消耗的 token 估算（prompt + completion）
            latency_ms: 调用耗时（毫秒）
            success: True=成功 / False=失败（计入 failure_count）
        """
        with _STATS_LOCK:
            STATS["total_tokens"] += max(0, int(tokens))
            STATS["total_latency_ms"] += max(0, int(latency_ms))
            if not success:
                STATS["failure_count"] += 1
            bucket = STATS["by_model"].setdefault(
                model_id,
                {"calls": 0, "tokens": 0, "latency_ms": 0, "failures": 0},
            )
            bucket["calls"] += 1
            bucket["tokens"] += max(0, int(tokens))
            bucket["latency_ms"] += max(0, int(latency_ms))
            if not success:
                bucket["failures"] += 1

    def get_stats(self) -> dict:
        """返回聚合统计快照。"""
        with _STATS_LOCK:
            total = STATS["total_calls"] or 1
            avg_latency = STATS["total_latency_ms"] / total
            return {
                "total_calls": STATS["total_calls"],
                "total_tokens": STATS["total_tokens"],
                "avg_latency_ms": round(avg_latency, 2),
                "failure_count": STATS["failure_count"],
                "by_model": dict(STATS["by_model"]),
            }

    def reset_stats(self) -> None:
        """重置统计（仅供测试使用）。"""
        with _STATS_LOCK:
            STATS["total_calls"] = 0
            STATS["total_tokens"] = 0
            STATS["total_latency_ms"] = 0
            STATS["failure_count"] = 0
            STATS["by_model"].clear()


# Singleton instance for module-level access
rate_limiter = NVIDIARateLimiter()
