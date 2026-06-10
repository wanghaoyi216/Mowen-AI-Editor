"""Agent SSE 路由 —— 订阅 ``AgentEventBus`` 并以 ``text/event-stream`` 推送。

端点：
  GET /projects/{project_id}/tasks/{task_id}/stream

支持：
  * ``Last-Event-ID`` header 断线重连：in-process 最近 100 事件缓存回放
  * 自动心跳（heartbeat）防止反向代理 / 网关 60s 超时切断
  * 任务结束时以 ``done`` 事件结束流（SSE 客户端会收到 ``event.data.type == "done"``）
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.models.ai_task import AITask
from app.services.agent_event_bus import bus


logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent-stream"])


@router.get("/projects/{project_id}/tasks/{task_id:int}/stream")
async def stream_task(
    project_id: int,
    task_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    """SSE 流式订阅任务执行事件。

    - 验证 task 是否属于该 project；不属于则 404。
    - 解析 ``Last-Event-ID`` header 作为断线重连游标（缺失则从最新事件开始）。
    - 返回 ``text/event-stream`` 响应，每个事件序列化为
      ``data: {json}\\n\\n``。
    - 任务 ``done`` 事件出现后立即结束流。
    """
    # 1. 验证 task 存在且属于指定 project
    task = (
        db.query(AITask)
        .filter(AITask.id == task_id, AITask.project_id == project_id)
        .first()
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    # 2. 解析 Last-Event-ID 头（断线重连）
    last_event_id = 0
    leh = request.headers.get("Last-Event-ID")
    if leh:
        try:
            last_event_id = int(leh)
        except ValueError:
            last_event_id = 0

    async def event_generator():
        try:
            async for event in bus.subscribe(task_id, last_event_id=last_event_id):
                # 客户端断开检测（FastAPI 会在 request.is_disconnected() 为 True
                # 时取消生成器；这里用 try/except CancelledError 兜底）
                if await request.is_disconnected():
                    logger.debug("SSE client disconnected: task_id=%s", task_id)
                    break
                yield event.to_sse()
                if event.event_type == "done":
                    break
        except asyncio.CancelledError:
            logger.debug("SSE generator cancelled: task_id=%s", task_id)
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# 说明：SSE 端点直接复用 ``AgentEvent.to_sse()`` 的 ``json.dumps(asdict(self))``
# 序列化路径，因此 ``event_type='text_delta'`` 事件（携带 ``data.delta`` 字段）
# 会被原样推送给前端；前端只需订阅 ``text_delta`` 即可按 delta 增量渲染。
# 无需在此文件额外做格式转换。
