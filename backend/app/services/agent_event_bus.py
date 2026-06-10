"""Agent Event Bus - 进程内 pub-sub 事件分发服务

用于 Agent 流式输出（Novel Orchestrator、SubAgent 等）在后台线程
和 FastAPI SSE 端点之间实时传递事件。

设计要点：
  * 同步 ``publish`` 入口兼容后台线程调用（``tasks.py`` 里的
    ``threading.Thread`` 也安全）。
  * 异步 ``subscribe`` 返回 ``AsyncIterator[AgentEvent]``，SSE 端点
    可以直接 ``async for`` 拉取并 yield 字节。
  * 每个 ``task_id`` 维护独立订阅者列表，互不干扰。
  * 最近 N 条事件 in-memory 缓存（默认 100），支持 SSE 的
    ``Last-Event-ID`` 断线重连回放。
  * 用 ``threading.Lock`` 保护订阅者与最近事件缓存，避免后台线程
    并发写导致列表损坏；asyncio.Queue 在事件循环线程中安全操作。
"""

import asyncio
import json
import logging
import threading
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Deque, Dict, Optional


logger = logging.getLogger(__name__)


@dataclass
class AgentEvent:
    """Agent 执行过程中发布的事件。

    字段：
      event_type: phase_start / phase_end / step_start / step_end /
                  tool_call / tool_result / tool_error / thinking / text_delta /
                  done / heartbeat
                  （text_delta 携带 LLM 流式增量文本：data={"delta": "<chunk>"};
                   业务调用方通常用 ``publish_text_delta`` 辅助方法发布；
                   tool_error 携带工具结构化失败：data={"tool", "error_code",
                   "remediation", "severity"}，severity 默认 "warning"，
                   业务调用方通常用 ``publish_tool_error`` 辅助方法发布）
      task_id:    关联的 AITask 主键
      timestamp:  ISO-8601 UTC 字符串
      phase:      当前阶段标识（planner / chapter_loop / reviewer）
      step:       当前步骤标识
      data:       任意 payload 字典（避免 dataclass 字段爆炸）
      event_id:   自增序号，由 AgentEventBus 在 publish 时填充，
                  用于 SSE 的 ``Last-Event-ID`` 断线重连
    """

    event_type: str
    task_id: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    phase: Optional[str] = None
    step: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    event_id: int = 0  # 自增，由 AgentEventBus 在 publish 时填充

    def to_sse(self) -> str:
        """序列化为 SSE 格式：``data: {json}\\n\\n``。"""
        return f"data: {json.dumps(asdict(self), ensure_ascii=False)}\n\n"


class AgentEventBus:
    """进程内事件总线：按 task_id 维护订阅者队列与最近事件缓存。"""

    def __init__(self, max_recent_per_task: int = 100) -> None:
        # task_id -> list[asyncio.Queue]
        self._subscribers: Dict[int, list[asyncio.Queue]] = {}
        # task_id -> deque[AgentEvent]（最近 N 条）
        self._recent: Dict[int, Deque[AgentEvent]] = {}
        # task_id -> 下一次分配的 event_id
        self._counter: Dict[int, int] = {}
        # 保护 _subscribers / _recent / _counter 的写操作
        self._lock = threading.Lock()
        self._max_recent = max_recent_per_task

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------
    def _next_event_id(self, task_id: int) -> int:
        with self._lock:
            self._counter[task_id] = self._counter.get(task_id, 0) + 1
            return self._counter[task_id]

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------
    def publish(self, event: AgentEvent) -> None:
        """同步发布事件（兼容后台线程调用）。

        行为：
          1. 分配自增 event_id。
          2. 写入最近事件缓存（容量受 max_recent_per_task 限制）。
          3. 拷贝当前订阅者列表，向每个 asyncio.Queue ``put_nowait``。
             队列满则静默丢弃（慢消费者降级）。
        """
        event.event_id = self._next_event_id(event.task_id)
        with self._lock:
            recent = self._recent.setdefault(
                event.task_id, deque(maxlen=self._max_recent)
            )
            recent.append(event)
            subscribers = list(self._subscribers.get(event.task_id, []))
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # 慢消费者：丢弃以避免阻塞发布者
                pass

    async def subscribe(
        self, task_id: int, last_event_id: int = 0
    ) -> AsyncIterator[AgentEvent]:
        """异步订阅 task 的事件流。

        ``last_event_id`` > 0 时先回放最近事件中 id 更大的部分（断线重连）。
        循环中以 60s 超时为周期发布 heartbeat 事件，避免反向代理超时
        切断连接；遇到 ``done`` 事件后退出。
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._lock:
            self._subscribers.setdefault(task_id, []).append(queue)
            # 断线重连：先把缓存中 > last_event_id 的事件灌入新队列
            if last_event_id > 0:
                for ev in self._recent.get(task_id, []):
                    if ev.event_id > last_event_id:
                        # 队列满则停止，避免阻塞锁
                        try:
                            queue.put_nowait(ev)
                        except asyncio.QueueFull:
                            break
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=60.0)
                except asyncio.TimeoutError:
                    # 心跳保活
                    yield AgentEvent(event_type="heartbeat", task_id=task_id)
                    continue
                if event.event_type == "done":
                    yield event
                    break
                yield event
        finally:
            with self._lock:
                subs = self._subscribers.get(task_id, [])
                if queue in subs:
                    subs.remove(queue)

    def close(self, task_id: int) -> None:
        """发布 done 事件，让所有订阅者退出。

        任务完成 / 失败 / 取消时由调用方触发。
        """
        self.publish(AgentEvent(event_type="done", task_id=task_id))
        with self._lock:
            self._subscribers.pop(task_id, None)


# ---------------------------------------------------------------------------
# 便利函数
# ---------------------------------------------------------------------------
def publish_text_delta(
    task_id: int | None,
    phase: str,
    agent: str,
    delta: str,
) -> None:
    """发布 ``text_delta`` 事件到总线（LLM 流式增量便捷入口）。

    参数：
        task_id: 关联的 AITask 主键；为 ``None`` 时不发送（向后兼容）
        phase:   当前阶段标识（planner / character_agent / plot_agent /
                 worldbook_agent / writer / reviewer / scene_decompose ...）
        agent:   发起方（与 ``phase`` 多数情况相同；当 SubAgent 与阶段不同
                 步时用此字段区分；前端会按 agent 把 delta 路由到对应卡片）
        delta:   增量文本片段（已通过 ``on_delta`` 拿到）

    行为：
        * 内部 try/except 包裹总线发布，发布失败不会影响调用方；
        * ``task_id`` 为 None / 0 时静默跳过，避免污染总线。
    """
    if task_id is None or not task_id:
        return
    if not delta:
        return
    try:
        bus.publish(
            AgentEvent(
                event_type="text_delta",
                task_id=task_id,
                phase=phase,
                step=agent,
                data={"delta": delta, "agent": agent, "phase": phase},
            )
        )
    except Exception as exc:  # noqa: BLE001 - 事件总线失败不能影响主流程
        logger.debug("publish_text_delta failed: task_id=%s, err=%s", task_id, exc)


def publish_tool_error(
    task_id: int | None,
    *,
    phase: str | None = None,
    tool: str,
    error_code: str,
    remediation: str,
    severity: str = "warning",
) -> None:
    """发布 ``tool_error`` 事件到总线（工具结构化失败便捷入口）。

    用于 B2 任务：B1 在 ``web_search_tool`` / ``web_scrape_tool`` 已经返回
    ``error_code`` / ``remediation`` 字段；编排链检测到该字段后通过本方法
    把失败广播到 ``AgentEventBus``，前端 AgentChat 收到后渲染黄色 toast
    （不阻断任务继续执行）。

    参数：
        task_id:     关联的 AITask 主键；为 ``None`` / 0 时静默跳过
        phase:       当前阶段标识（如 ``research`` / ``planner``）
        tool:        工具名（如 ``web_search`` / ``web_scrape``）
        error_code:  结构化错误码（如 ``MISSING_TAVILY_KEY``）
        remediation: 中文修复建议
        severity:    严重程度，默认 ``"warning"``，可选 ``"error"``

    行为：
        * 内部 try/except 包裹总线发布，发布失败不会影响调用方；
        * ``task_id`` 为 None / 0 时静默跳过，避免污染总线；
        * 不抛异常，调用方可在业务主流程中安全调用。
    """
    if task_id is None or not task_id:
        return
    if not error_code:
        return
    if severity not in {"warning", "error"}:
        severity = "warning"
    try:
        bus.publish(
            AgentEvent(
                event_type="tool_error",
                task_id=task_id,
                phase=phase,
                data={
                    "tool": tool,
                    "error_code": error_code,
                    "remediation": remediation or "",
                    "severity": severity,
                },
            )
        )
    except Exception as exc:  # noqa: BLE001 - 事件总线失败不能影响主流程
        logger.debug("publish_tool_error failed: task_id=%s, err=%s", task_id, exc)


# 进程内单例：所有模块共享同一个总线
bus = AgentEventBus()
