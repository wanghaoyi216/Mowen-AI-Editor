import json
import logging
import threading
from datetime import datetime, timezone


class TaskCancellationRegistry:
    """Simple in-process cancellation registry for tracking cancelled tasks."""

    def __init__(self) -> None:
        self._cancelled: set[int] = set()
        self._locks: dict[int, threading.Lock] = {}
        self._registry_lock = threading.Lock()

    def cancel(self, task_id: int) -> None:
        with self._registry_lock:
            self._cancelled.add(task_id)
            lock = self._locks.get(task_id)
            if lock is not None:
                lock.acquire(blocking=False)
                lock.release()

    def is_cancelled(self, task_id: int) -> bool:
        with self._registry_lock:
            return task_id in self._cancelled

    def get_lock(self, task_id: int) -> threading.Lock:
        with self._registry_lock:
            lock = self._locks.get(task_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[task_id] = lock
            return lock

    def clear(self, task_id: int) -> None:
        with self._registry_lock:
            self._cancelled.discard(task_id)
            self._locks.pop(task_id, None)


task_cancellation_registry = TaskCancellationRegistry()

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.db.base import SessionLocal
from app.schemas.ai_task import AITaskCreate, AITaskRead, TaskStepCreate, TaskStepRead
from app.schemas.chapter import ChapterRead
from app.schemas.chapter_version import ChapterVersionRead
from app.schemas.common import ApiResponse
from app.schemas.react_executor import MinimalReActExecutionRequest
from app.schemas.task_log import TaskLogRead
from app.schemas.trend_execution import TrendExecutionRequest
from app.schemas.task_runtime import (
    TaskControlRequest,
    TaskRuntimeState,
    TaskStatusUpdate,
    TaskStepRuntimeState,
    TaskStepStatusUpdate,
)
from app.schemas.workflow_orchestration import AutoNovelWorkflowRequest
from app.schemas.character import CharacterRead
from app.schemas.plot_line import PlotLineRead
from app.schemas.trend_exploration import TrendExplorationRead
from app.schemas.worldbook_entry import WorldbookEntryRead
from app.services.react_executor_service import execute_minimal_react_task, execute_trend_react_task
from app.services.task_runtime_service import (
    control_task_runtime_state,
    get_or_rebuild_task_runtime_state,
    get_or_rebuild_task_step_runtime_states,
    get_task_tool_errors,
    set_task_runtime_state,
    set_task_step_runtime_state,
)
from app.services.task_persistence_service import TaskPersistenceManager
from app.services.task_service import create_task, create_task_step, create_task_log, delete_task, get_task_logs, list_task_steps, list_tasks
from app.services.task_service import get_task
from app.services.workflow_orchestration_service import execute_auto_novel_workflow
from app.services.novel_orchestrator_service import execute_novel_workflow


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{project_id}/tasks", response_model=ApiResponse)
def read_tasks(project_id: int, chapter_id: int | None = None, db: Session = Depends(get_db_session)) -> ApiResponse:
    items = list_tasks(db, project_id, chapter_id)
    return ApiResponse(data=[AITaskRead.model_validate(item) for item in items])


@router.post("/{project_id}/tasks", response_model=ApiResponse)
def create_task_endpoint(
    project_id: int,
    payload: AITaskCreate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = create_task(db, project_id, payload)
    return ApiResponse(message="task created", data=AITaskRead.model_validate(item))


@router.delete("/{project_id}/tasks/{task_id:int}", response_model=ApiResponse)
def delete_task_endpoint(
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    success = delete_task(db, project_id, task_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return ApiResponse(message="task deleted", data={"id": task_id})


@router.post("/{project_id}/tasks/execute-react", response_model=ApiResponse)
def execute_react_task_endpoint(
    project_id: int,
    payload: MinimalReActExecutionRequest,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    result = execute_minimal_react_task(
        db,
        project_id=project_id,
        title=payload.title,
        module_type=payload.module_type,
        objective=payload.objective,
        chapter_id=payload.chapter_id,
        plot_line_id=payload.plot_line_id,
    )
    return ApiResponse(
        message="react task executed",
        data={
            "task": AITaskRead.model_validate(result["task"]),
            "steps": [TaskStepRead.model_validate(step) for step in result["steps"]],
        },
    )


@router.post("/{project_id}/tasks/execute-trend-react", response_model=ApiResponse)
def execute_trend_react_task_endpoint(
    project_id: int,
    payload: TrendExecutionRequest,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    result = execute_trend_react_task(
        db,
        project_id=project_id,
        title=payload.title,
        query_text=payload.query_text,
        source_scope=payload.source_scope,
    )
    return ApiResponse(
        message="trend react task executed",
        data={
            "task": AITaskRead.model_validate(result["task"]),
            "steps": [TaskStepRead.model_validate(step) for step in result["steps"]],
            "trend": result["trend"].id,
            "llm_message": result["llm_message"],
        },
    )


@router.post("/{project_id}/tasks/execute-auto-novel-workflow", response_model=ApiResponse)
def execute_auto_novel_workflow_endpoint(
    project_id: int,
    payload: AutoNovelWorkflowRequest,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    if not payload.title:
        payload.title = "AI自主决定题材"

    if not payload.query_text:
        payload.query_text = "当前热门网络小说题材趋势分析 2026"

    from app.services.task_service import create_task as _create_task
    from app.schemas.ai_task import AITaskCreate as _AITaskCreate
    from app.services.task_service import create_task_step as _create_task_step

    task = _create_task(
        db,
        project_id,
        _AITaskCreate(
            chapter_id=payload.chapter_id,
            task_type="auto_novel_workflow",
            module_type="novel_orchestration",
            title=payload.title,
            input_payload=f"题材: {payload.query_text} | 篇幅: {payload.novel_length}",
            plan_text="Novel Planner → Chapter Loop (逐章生成) → Novel Reviewer",
            status="running",
        ),
    )

    # 创建反映三阶段编排架构的步骤
    step_specs = [
        (1, "Novel Planner", "novel_planner", "reason", "AI 生成完整小说大纲（标题、题材、章节规划、主要角色）"),
        (2, "Chapter Generation Loop", "chapter_loop", "loop", f"逐章调用工作流生成正文（篇幅偏好: {payload.novel_length}）"),
        (3, "Novel Reviewer", "novel_reviewer", "observe", "全文一致性审查（角色、剧情、世界观）"),
    ]

    for step_no, step_name, step_type, react_state, input_payload in step_specs:
        _create_task_step(
            db,
            project_id,
            task.id,
            step_no=step_no,
            step_name=step_name,
            step_type=step_type,
            react_state=react_state,
            status="running" if step_no == 1 else "pending",
            input_payload=input_payload,
        )

    set_task_runtime_state(
        project_id,
        task.id,
        TaskStatusUpdate(status="running", current_step="novel_planner", message="Novel Orchestrator 工作流已启动"),
    )

    def _run_workflow_background():
        bg_db = SessionLocal()
        try:
            result = execute_novel_workflow(
                db=bg_db,
                project_id=project_id,
                topic=payload.query_text,
                novel_length=payload.novel_length,
                style_hint=payload.style_hint,
                revision_focus=payload.revision_focus,
                task_id=task.id,
                book_id=payload.book_id,
            )

            # 更新任务状态
            finished_task = get_task(bg_db, project_id, task.id)
            if finished_task is not None:
                outline_info = result.get("novel_outline", {})
                chapters_count = outline_info.get("chapters_count", 0)
                elapsed = result.get("elapsed_seconds", 0)
                # 检查是否被取消
                if task_cancellation_registry.is_cancelled(task.id):
                    finished_task.status = "cancelled"
                    finished_task.error_message = "用户取消"
                else:
                    finished_task.status = "completed" if result.get("status") == "completed" else "partial"
                finished_task.output_payload = json.dumps({
                    "workflow_id": result.get("workflow_id", ""),
                    "novel_title": outline_info.get("title", ""),
                    "genre": outline_info.get("genre", ""),
                    "target_chapters": chapters_count,
                    "total_words": result.get("phases", {}).get("chapter_loop", {}).get("total_words", 0),
                    "elapsed_seconds": elapsed,
                }, ensure_ascii=False)[:2000]
                finished_task.finished_at = finished_task.finished_at or datetime.now(timezone.utc)
                bg_db.add(finished_task)
                bg_db.commit()

            logger.info("Novel Orchestrator completed: task_id=%s, status=%s, chapters=%d", task.id, result.get("status"), chapters_count)

            # 更新运行时状态，反映实际的章节数
            if chapters_count > 0:
                set_task_runtime_state(
                    project_id,
                    task.id,
                    TaskStatusUpdate(
                        status=result.get("status", "completed"),
                        current_step="novel_reviewer",
                        message=f"全部 {chapters_count} 章生成完成",
                    ),
                )
        except Exception as exc:
            logger.error("Novel Orchestrator failed: task_id=%s, error=%s", task.id, exc, exc_info=True)
            failed_task = get_task(bg_db, project_id, task.id)
            if failed_task is not None:
                if task_cancellation_registry.is_cancelled(task.id):
                    failed_task.status = "cancelled"
                    failed_task.error_message = "用户取消"
                else:
                    failed_task.status = "failed"
                    failed_task.error_message = str(exc)[:500]
                failed_task.finished_at = failed_task.finished_at or datetime.now(timezone.utc)
                bg_db.add(failed_task)
                bg_db.commit()
            set_task_runtime_state(
                project_id,
                task.id,
                TaskStatusUpdate(
                    status="cancelled" if task_cancellation_registry.is_cancelled(task.id) else "failed",
                    current_step="error",
                    message="用户取消" if task_cancellation_registry.is_cancelled(task.id) else str(exc)[:300],
                ),
            )
        finally:
            # 清理取消标记 + 用户指示
            task_cancellation_registry.clear(task.id)
            try:
                from app.services.user_message_registry import user_message_registry
                user_message_registry.clear(task.id)
            except Exception:  # noqa: BLE001
                pass
            TaskPersistenceManager.unregister_active_thread(task.id)
            bg_db.close()

    thread = threading.Thread(target=_run_workflow_background, daemon=True)
    TaskPersistenceManager.register_active_thread(task.id, thread)
    thread.start()

    return ApiResponse(
        message="novel orchestrator workflow started in background",
        data={
            "task": AITaskRead.model_validate(task),
            "steps": [TaskStepRead.model_validate(step) for step in list_task_steps(db, task.id)],
            "workflow_architecture": {
                "type": "novel_orchestrator",
                "phases": ["Novel Planner", "Chapter Generation Loop", "Novel Reviewer"],
                "novel_length": payload.novel_length,
            },
        },
    )


@router.get("/{project_id}/tasks/{task_id:int}", response_model=ApiResponse)
def read_task(project_id: int, task_id: int, db: Session = Depends(get_db_session)) -> ApiResponse:
    item = get_task(db, project_id, task_id)
    return ApiResponse(data=AITaskRead.model_validate(item) if item else None)


@router.get("/{project_id}/tasks/{task_id:int}/steps", response_model=ApiResponse)
def read_task_steps(project_id: int, task_id: int, db: Session = Depends(get_db_session)) -> ApiResponse:
    _ = project_id
    items = list_task_steps(db, task_id)
    return ApiResponse(data=[TaskStepRead.model_validate(item) for item in items])


@router.post("/{project_id}/tasks/{task_id:int}/steps", response_model=ApiResponse)
def create_task_step_endpoint(
    project_id: int,
    task_id: int,
    payload: TaskStepCreate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = create_task_step(db, project_id, task_id, **payload.model_dump())
    return ApiResponse(message="task step created", data=TaskStepRead.model_validate(item))


@router.get("/{project_id}/tasks/{task_id:int}/runtime", response_model=ApiResponse)
def read_task_runtime(project_id: int, task_id: int, db: Session = Depends(get_db_session)) -> ApiResponse:
    state = get_or_rebuild_task_runtime_state(db, project_id, task_id)
    return ApiResponse(data=state)


@router.post("/{project_id}/tasks/{task_id:int}/runtime", response_model=ApiResponse)
def update_task_runtime(project_id: int, task_id: int, payload: TaskStatusUpdate) -> ApiResponse:
    state = set_task_runtime_state(project_id, task_id, payload)
    return ApiResponse(message="task runtime updated", data=TaskRuntimeState.model_validate(state))


@router.post("/{project_id}/tasks/{task_id:int}/cancel", response_model=ApiResponse)
def cancel_task_endpoint(
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    """请求取消正在运行的任务。

    幂等行为：
    - 任务已是 ``cancelling`` / ``cancelled`` 状态：返回 200 + 友好消息
      （不抛 400），方便前端连点取消按钮。
    - 任务处于 ``running`` / ``pending``：标记 ``cancelling`` 并通知 runtime。
    - 其他状态：返回 400。
    """
    task = get_task(db, project_id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    # 幂等：重复请求取消不报错
    if task.status in ("cancelling", "cancelled"):
        return ApiResponse(
            message="任务取消已请求，重复请求幂等返回",
            data=AITaskRead.model_validate(task),
        )
    if task.status not in ("running", "pending"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"任务状态为 {task.status}，无法取消")

    # 标记取消
    task_cancellation_registry.cancel(task_id)

    # 更新数据库状态
    task.status = "cancelling"
    db.add(task)
    db.commit()
    db.refresh(task)

    # 通知 runtime
    set_task_runtime_state(
        project_id,
        task_id,
        TaskStatusUpdate(
            status="cancelling",
            current_step="cancellation_requested",
            message="任务取消已请求，等待后台线程退出",
        ),
    )

    return ApiResponse(message="task cancellation requested", data=AITaskRead.model_validate(task))


@router.post("/{project_id}/tasks/{task_id:int}/message", response_model=ApiResponse)
def send_task_message(
    project_id: int,
    task_id: int,
    payload: dict,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    """作者向运行中的 AI 任务发送实时指示 / 消息。

    行为：
      1. 校验任务存在。
      2. 把消息推入 ``user_message_registry``，后台编排线程在下一章创作前
         ``drain`` 出来注入写作上下文（实时引导创作方向）。
      3. 立刻向 AgentEventBus 推送 ``user_message`` 事件（前端气泡即时显示）
         + 一条 ``assistant_ack`` 确认，并落库 TaskLog 留痕。
    """
    from app.services.agent_event_bus import AgentEvent, bus
    from app.services.user_message_registry import user_message_registry

    message = str(payload.get("message", "") if isinstance(payload, dict) else "").strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="消息不能为空")

    task = get_task(db, project_id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    is_active = task.status in ("running", "pending", "paused")
    if is_active:
        user_message_registry.push(task_id, message)

    # 留痕 + 即时事件
    try:
        create_task_log(db, task_id, step_no=None, log_type="user_message", message=message)
    except Exception:  # noqa: BLE001
        pass
    try:
        bus.publish(AgentEvent(event_type="user_message", task_id=task_id, phase="chat", data={"text": message}))
        ack = (
            "已收到你的指示，将在后续章节创作中采纳。"
            if is_active
            else "已记录你的留言。该任务当前未在运行，可启动 / 继续创作后生效。"
        )
        bus.publish(AgentEvent(event_type="assistant_ack", task_id=task_id, phase="chat", data={"text": ack}))
    except Exception:  # noqa: BLE001
        pass

    return ApiResponse(
        message="message accepted",
        data={"task_id": task_id, "accepted": is_active, "queued": is_active},
    )


@router.get("/{project_id}/tasks/models", response_model=ApiResponse)
def list_available_models() -> ApiResponse:
    """列出可用的 LLM 模型及其元信息。"""
    from app.core.config import settings
    fallback_list = [m.strip() for m in settings.nvidia_fallback_models.split(",") if m.strip()]
    return ApiResponse(
        message="available LLM models",
        data={
            "primary": settings.nvidia_primary_model,
            "creator_model": settings.creator_model,
            "subagent_model": settings.controller_model,
            "fallback_chain": fallback_list,
            "provider": "nvidia",
            "features": {
                "rate_limit_per_minute": getattr(settings, "rate_limit_calls_per_minute", 40),
                "long_context_window": True,
                "json_mode_supported": True,
                "max_concurrent_tasks": 1,
            },
            "model_info": {
                "nvidia/nemotron-3-ultra-550b-a55b": {
                    "context_window": 1048576,
                    "best_for": ["长篇小说创作", "跨章节一致性", "大纲与全文上下文整合"],
                    "speed": "medium",
                    "role": "主创作模型（正文）",
                },
                "minimaxai/minimax-m2.7": {
                    "context_window": 245760,
                    "best_for": ["子 Agent 规划", "角色/剧情/世界观设计", "审稿与一致性", "结构化 JSON 输出"],
                    "speed": "fast",
                    "role": "子 Agent / 控制模型",
                },
                "nvidia/llama-3.1-nemotron-70b-instruct": {
                    "context_window": 131072,
                    "best_for": ["长上下文推理", "规划与审稿"],
                    "speed": "medium",
                },
                "meta/llama-3.1-70b-instruct": {
                    "context_window": 131072,
                    "best_for": ["长篇创作", "复杂推理"],
                    "speed": "medium",
                },
                "qwen/qwen-2.5-72b-instruct": {
                    "context_window": 32768,
                    "best_for": ["中文创作", "结构化输出"],
                    "speed": "fast",
                },
                "mistralai/mixtral-8x22b-instruct": {
                    "context_window": 65536,
                    "best_for": ["创意写作", "多语言"],
                    "speed": "medium",
                },
            },
        },
    )


@router.get("/{project_id}/tasks/concurrency", response_model=ApiResponse)
def get_task_concurrency_status(project_id: int, db: Session = Depends(get_db_session)) -> ApiResponse:
    """获取当前项目的并发任务状态。"""
    from sqlalchemy import func, select
    from app.models.ai_task import AITask

    stmt = (
        select(AITask.status, func.count(AITask.id))
        .where(AITask.project_id == project_id)
        .group_by(AITask.status)
    )
    rows = db.execute(stmt).all()
    counts = {row[0]: int(row[1]) for row in rows}
    running = counts.get("running", 0)
    pending = counts.get("pending", 0)
    return ApiResponse(
        message="concurrency status",
        data={
            "max_concurrent": 1,
            "current_running": running,
            "current_pending": pending,
            "available_slots": max(0, 1 - running),
            "by_status": counts,
        },
    )


@router.post("/{project_id}/tasks/{task_id:int}/control", response_model=ApiResponse)
def control_task_runtime(
    project_id: int,
    task_id: int,
    payload: TaskControlRequest,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    try:
        state = control_task_runtime_state(project_id, task_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    task = get_task(db, project_id, task_id)
    if task is not None:
        task.status = state.status
        db.add(task)
        db.commit()
        db.refresh(task)
    return ApiResponse(message=f"task {payload.action} applied", data=TaskRuntimeState.model_validate(state))


@router.get("/{project_id}/tasks/{task_id:int}/step-runtime", response_model=ApiResponse)
def read_task_step_runtime(project_id: int, task_id: int, db: Session = Depends(get_db_session)) -> ApiResponse:
    states = get_or_rebuild_task_step_runtime_states(db, project_id, task_id)
    return ApiResponse(data=[TaskStepRuntimeState.model_validate(state) for state in states])


@router.post("/{project_id}/tasks/{task_id:int}/step-runtime", response_model=ApiResponse)
def update_task_step_runtime(project_id: int, task_id: int, payload: TaskStepStatusUpdate) -> ApiResponse:
    state = set_task_step_runtime_state(project_id, task_id, payload)
    return ApiResponse(message="task step runtime updated", data=TaskStepRuntimeState.model_validate(state))


@router.get("/{project_id}/tasks/{task_id:int}/tool-errors", response_model=ApiResponse)
def read_task_tool_errors(
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    """读取任务的工具错误列表。

    优先从 ``task.summary.tool_errors`` 读取（如有）；当 AITask 模型尚未
    持久化 ``summary`` 字段时（当前实现），降级到 Redis runtime state
    ``novel-ai-editor:project:<project_id>:task:<task_id>:tool_errors``。
    任务运行期间记录（B2 任务）和完成后短期内都可读取。
    """
    task = get_task(db, project_id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # 1) 优先尝试 task.summary 字段（schema 中可能尚未启用）
    tool_errors: list = []
    summary: object = getattr(task, "summary", None)
    if summary:
        if isinstance(summary, str):
            try:
                summary = json.loads(summary)
            except json.JSONDecodeError:
                summary = {}
        if isinstance(summary, dict):
            raw_errors = summary.get("tool_errors")
            if isinstance(raw_errors, list):
                tool_errors = [item for item in raw_errors if isinstance(item, dict)]

    # 2) Fallback 到 Redis runtime state（B2 维护的列表）
    if not tool_errors:
        try:
            tool_errors = get_task_tool_errors(project_id, task_id) or []
        except Exception:  # noqa: BLE001 - Redis 不可用时不阻断读路径
            tool_errors = []

    return ApiResponse(
        message="task tool errors retrieved",
        data={
            "tool_errors": tool_errors,
            "count": len(tool_errors),
        },
    )


@router.get("/{project_id}/tasks/{task_id:int}/logs", response_model=ApiResponse)
def get_task_logs_endpoint(
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db_session),
    limit: int = 100,
) -> ApiResponse:
    task = get_task(db, project_id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    logs = get_task_logs(db, task_id, limit=limit)
    return ApiResponse(
        message="task logs retrieved",
        data=[TaskLogRead.model_validate(log) for log in logs],
    )


@router.post("/{project_id}/tasks/{task_id:int}/resume", response_model=ApiResponse, status_code=status.HTTP_202_ACCEPTED)
def resume_task_endpoint(
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    """从最近的检查点恢复任务。

    允许 ``paused`` / ``failed`` / ``cancelled`` / ``partial`` 状态的任务恢复；读取
    ``task_checkpoints`` 中最近一条记录的 ``last_chapter_no`` 计算
    ``start_chapter``，然后在后台线程中复用 ``execute_novel_workflow``，
    把 ``accumulated_context`` 透传给编排器以种入历史摘要与角色档案。
    """
    # 1. 验证 task 存在
    task = get_task(db, project_id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if TaskPersistenceManager.is_thread_active(task_id):
        state = control_task_runtime_state(
            project_id,
            task_id,
            TaskControlRequest(action="resume", message="继续运行当前仍存活的后台线程"),
            db=db,
        )
        return ApiResponse(
            message="task runtime resumed",
            data=TaskRuntimeState.model_validate(state),
        )

    # 2. 仅允许可恢复状态恢复
    if task.status not in ("paused", "failed", "cancelled", "partial", "cancelling"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务状态为 {task.status}，无需恢复",
        )

    # 3. 读取最近 checkpoint
    persistence_mgr = TaskPersistenceManager()
    checkpoint = persistence_mgr.load_latest_checkpoint(task_id)
    if checkpoint is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未找到检查点，无法恢复",
        )

    start_chapter = (checkpoint.last_chapter_no or 0) + 1
    accumulated = checkpoint.accumulated_context or {}

    # 把任务标记回 running 状态并通知 runtime
    task.status = "running"
    db.add(task)
    db.commit()
    db.refresh(task)

    set_task_runtime_state(
        project_id,
        task_id,
        TaskStatusUpdate(
            status="running",
            current_step="chapter_loop",
            message=f"从第 {start_chapter} 章恢复（检查点: {checkpoint.current_phase}）",
        ),
    )

    # 4. 启动后台线程
    def _run_resume_background() -> None:
        bg_db = SessionLocal()
        try:
            result = execute_novel_workflow(
                db=bg_db,
                project_id=project_id,
                topic=accumulated.get("outline_title", task.title or ""),
                novel_length="ai_decided",
                style_hint=None,
                revision_focus=None,
                task_id=task_id,
                start_chapter=start_chapter,
                accumulated_context=accumulated,
            )

            finished_task = get_task(bg_db, project_id, task_id)
            if finished_task is not None:
                if task_cancellation_registry.is_cancelled(task_id):
                    finished_task.status = "cancelled"
                else:
                    finished_task.status = (
                        "completed" if result.get("status") == "completed" else "partial"
                    )
                finished_task.finished_at = finished_task.finished_at or datetime.now(timezone.utc)
                bg_db.add(finished_task)
                bg_db.commit()

            logger.info(
                "Resume completed: task_id=%s, status=%s",
                task_id,
                result.get("status"),
            )
        except Exception as exc:
            logger.error(
                "Resume failed: task_id=%s, error=%s",
                task_id,
                exc,
                exc_info=True,
            )
            failed_task = get_task(bg_db, project_id, task_id)
            if failed_task is not None:
                if task_cancellation_registry.is_cancelled(task_id):
                    failed_task.status = "cancelled"
                    failed_task.error_message = "用户取消"
                else:
                    failed_task.status = "failed"
                    failed_task.error_message = str(exc)[:500]
                failed_task.finished_at = failed_task.finished_at or datetime.now(timezone.utc)
                bg_db.add(failed_task)
                bg_db.commit()
        finally:
            task_cancellation_registry.clear(task_id)
            TaskPersistenceManager.unregister_active_thread(task_id)
            bg_db.close()

    thread = threading.Thread(target=_run_resume_background, daemon=True)
    TaskPersistenceManager.register_active_thread(task_id, thread)
    thread.start()

    return ApiResponse(
        message="task resume started",
        data={
            "task_id": task_id,
            "start_chapter": start_chapter,
            "checkpoint_phase": checkpoint.current_phase,
            "restored_summaries": len(accumulated.get("previous_chapters_summary") or []),
            "restored_profiles": len(accumulated.get("character_profiles") or {}),
        },
    )


@router.get("/{project_id}/tasks/llm-stats", response_model=ApiResponse)
def get_llm_stats_endpoint() -> ApiResponse:
    """获取 LLM 调用统计。"""
    from app.services.rate_limiter import rate_limiter
    return ApiResponse(message="llm call statistics", data=rate_limiter.get_stats())


@router.post("/tasks/cleanup-orphans", response_model=ApiResponse)
def cleanup_orphan_tasks_endpoint() -> ApiResponse:
    """手动清理 orphan task：把 DB 里 ``status=running`` 但实际 worker 已死的
    任务（daemon thread OOM / LLM 流式 hang 死 / 容器重启等场景）批量标为
    ``paused``。用户拿到结果后可对单个 task 调 ``POST /tasks/{id}/resume`` 续跑。

    启动时 main.py 也会自动跑一次，这里作为运维兜底接口。
    """
    paused_ids = TaskPersistenceManager().mark_orphaned_tasks_as_paused()
    return ApiResponse(
        message=f"清理完成，共将 {len(paused_ids)} 个 orphan task 标为 paused",
        data={"paused_ids": paused_ids, "count": len(paused_ids)},
    )
