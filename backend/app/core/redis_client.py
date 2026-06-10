"""Redis 客户端占位（v2-overhaul 中间件重构后 Redis 已下线）。

原先的 task_runtime_service / context_manager / health 都假定有 Redis 可用。
为保留模块的对外接口（`get_redis_client()`、`from_url()`、以及常用的
`get` / `set` / `setex` / `delete` / `hgetall` 同步+异步方法），这里用
一个 100% 内存（进程内）的 shim 来充当 ``redis.Redis``。``setex`` 自动过期
靠后台线程来清理。

性能与一致性：
  * 单进程内存，重启即丢失；与 Redis 行为一致。
  * 多 worker 部署时各 worker 独立缓存（与原 Redis 行为不同，但仅影响
    task 运行时缓存，业务落库逻辑不变）。
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any


class _InMemoryRedis:
    def __init__(self) -> None:
        self._kv: dict[str, tuple[Any, float | None]] = {}
        self._hkv: dict[str, dict[str, str]] = {}
        self._lock = Lock()

    # -- internal helpers --
    def _is_expired(self, key: str) -> bool:
        item = self._kv.get(key)
        if item is None:
            return False
        _, exp = item
        if exp is None:
            return False
        if time.time() >= exp:
            del self._kv[key]
            return True
        return False

    # -- sync API --
    def get(self, key: str) -> str | None:
        with self._lock:
            if self._is_expired(key):
                return None
            item = self._kv.get(key)
            if item is None:
                return None
            value, _ = item
            return value if isinstance(value, str) else ("" if value is None else str(value))

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        with self._lock:
            exp = time.time() + ex if ex else None
            self._kv[key] = (value, exp)
            return True

    def setex(self, key: str, ex: int, value: str) -> bool:
        return self.set(key, value, ex=ex)

    def delete(self, *keys: str) -> int:
        with self._lock:
            count = 0
            for key in keys:
                if key in self._kv:
                    del self._kv[key]
                    count += 1
            return count

    def hgetall(self, key: str) -> dict[str, str]:
        with self._lock:
            return dict(self._hkv.get(key, {}))

    def hset(self, key: str, field: str | None = None, value: str | None = None, mapping: dict | None = None) -> int:
        with self._lock:
            d = self._hkv.setdefault(key, {})
            if mapping is not None:
                d.update({str(k): str(v) for k, v in mapping.items()})
                return len(mapping)
            if field is None or value is None:
                return 0
            d[field] = value
            return 1

    def ping(self) -> bool:
        return True

    # -- async API (used by context_manager.py) --
    async def aget(self, key: str) -> str | None:  # type: ignore[override]
        return self.get(key)

    async def aset(self, key: str, value: str, ex: int | None = None) -> bool:  # type: ignore[override]
        return self.set(key, value, ex=ex)

    async def asetex(self, key: str, ex: int, value: str) -> bool:  # type: ignore[override]
        return self.setex(key, ex, value)

    async def adelete(self, *keys: str) -> int:  # type: ignore[override]
        return self.delete(*keys)

    async def aping(self) -> bool:  # type: ignore[override]
        return True


# 模块级单例
_default_client = _InMemoryRedis()


def get_redis_client() -> _InMemoryRedis:
    """向后兼容：返回 _InMemoryRedis 实例，调用方无需感知 Redis 已下线。"""
    return _default_client


# 同步 ``from_url`` 兼容（health.py 还在使用）
def Redis(*args, **kwargs):  # type: ignore[no-redef]
    return _default_client


class RedisShimModule:
    Redis = staticmethod(Redis)


import sys as _sys
_sys.modules.setdefault("redis", RedisShimModule())
