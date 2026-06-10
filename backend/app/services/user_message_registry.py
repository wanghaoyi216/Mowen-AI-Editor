"""用户实时指示注册表（进程内）。

让作者在 AI 创作任务运行期间向其发送消息 / 指示。后台编排线程在每章创作前
``drain`` 出待处理指示，注入到写作上下文，实现"作者与 AI 实时交互、引导创作"。

设计与 ``TaskCancellationRegistry`` 一致：纯内存 + 线程锁，足够轻量；
指示本身是临时引导信号，无需持久化（已通过 TaskLog 落库做留痕）。
"""

from __future__ import annotations

import threading
from collections import defaultdict


class UserMessageRegistry:
    def __init__(self) -> None:
        self._pending: dict[int, list[str]] = defaultdict(list)
        self._lock = threading.Lock()

    def push(self, task_id: int, message: str) -> None:
        message = (message or "").strip()
        if not message:
            return
        with self._lock:
            self._pending[task_id].append(message)

    def drain(self, task_id: int) -> list[str]:
        """取出并清空某任务的待处理指示。"""
        with self._lock:
            msgs = self._pending.get(task_id, [])
            self._pending[task_id] = []
            return list(msgs)

    def has_pending(self, task_id: int) -> bool:
        with self._lock:
            return bool(self._pending.get(task_id))

    def clear(self, task_id: int) -> None:
        with self._lock:
            self._pending.pop(task_id, None)


user_message_registry = UserMessageRegistry()
