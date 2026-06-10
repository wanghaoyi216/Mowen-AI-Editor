"""测试 ``TaskCancellationRegistry`` 内存级任务取消注册表。

该注册表用于跟踪用户取消的 task，并提供与 task_id 一一对应的 ``threading.Lock``，
便于后台工作线程在 ``get_lock(task_id).acquire()`` 上阻塞等待取消信号。

覆盖：
- ``cancel`` / ``is_cancelled`` 基础往返
- 多 task 状态互相独立
- ``get_lock`` 同一 task 返回同一 lock，不同 task 返回不同 lock
- ``clear`` 后 ``get_lock`` 会重建新 lock
"""

from __future__ import annotations

import threading

from app.api.routes.tasks import TaskCancellationRegistry


def test_registry_cancel_and_is_cancelled():
    """基本往返：cancel 之后 is_cancelled 为 True，clear 之后为 False。"""
    reg = TaskCancellationRegistry()
    assert not reg.is_cancelled(1)
    reg.cancel(1)
    assert reg.is_cancelled(1)
    reg.clear(1)
    assert not reg.is_cancelled(1)


def test_registry_multiple_tasks_independent():
    """多个 task 的取消状态互相独立。"""
    reg = TaskCancellationRegistry()
    reg.cancel(1)
    reg.cancel(2)
    assert reg.is_cancelled(1)
    assert reg.is_cancelled(2)
    reg.clear(1)
    assert not reg.is_cancelled(1)
    assert reg.is_cancelled(2)


def test_registry_get_lock_returns_lock():
    """同一 task_id 多次 ``get_lock`` 应返回同一 ``threading.Lock`` 实例。"""
    reg = TaskCancellationRegistry()
    lock1 = reg.get_lock(1)
    lock2 = reg.get_lock(1)
    # threading.Lock 是工厂函数，type(lock1) 才是 _thread.lock 类型
    assert type(lock1).__name__ == "lock"
    assert lock1 is lock2

    # 不同 task 应返回不同 lock
    lock3 = reg.get_lock(2)
    assert lock1 is not lock3


def test_registry_clear_removes_lock():
    """``clear`` 后再 ``get_lock`` 会创建新的 lock（不会复用旧的）。"""
    reg = TaskCancellationRegistry()
    old_lock = reg.get_lock(1)
    reg.clear(1)
    new_lock = reg.get_lock(1)
    # clear 之后旧 lock 引用从内部表移除，get_lock 会生成新 lock
    assert new_lock is not None
    assert new_lock is not old_lock
