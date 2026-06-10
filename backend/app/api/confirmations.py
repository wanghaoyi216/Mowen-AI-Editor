"""阶段确认相关 API 路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AITask
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.confirmation import (
    ApproveConfirmationRequest,
    ChainExecutionStatus,
    ConfirmationResponse,
    SetModeRequest,
)
from app.services.confirmation_engine import (
    approve_confirmation,
    get_confirmation_history,
    get_pending_confirmation,
    set_task_mode,
    skip_confirmation,
)

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}", tags=["确认"])


@router.get(
    "/confirmation",
    summary="获取当前等待确认的信息",
    description="获取当前任务在哪个确认点等待用户确认，包含阶段成果摘要",
    response_model=ApiResponse[ConfirmationResponse | None],
)
async def get_confirmation(
    project_id: int,
    task_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取当前等待确认的信息"""
    result = await get_pending_confirmation(db, task_id)
    if result is None:
        return ApiResponse(success=True, message="无待确认信息", data=None)
    return ApiResponse(success=True, message="ok", data=ConfirmationResponse(**result))


@router.post(
    "/confirmation/approve",
    summary="确认并继续",
    description="用户确认当前阶段成果，AI 继续执行下一阶段。可选择输入补充建议指导后续创作",
    response_model=ApiResponse[dict],
)
async def approve(
    project_id: int,
    task_id: int,
    body: ApproveConfirmationRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """确认并继续"""
    human_input = body.human_input if body else None
    success = await approve_confirmation(db, task_id, human_input)
    if not success:
        raise HTTPException(status_code=404, detail="No pending confirmation found")
    return ApiResponse(success=True, message="已确认，继续执行", data={"approved": True})


@router.post(
    "/confirmation/skip",
    summary="跳过当前阶段",
    description="跳过当前确认点，AI 继续执行下一阶段",
    response_model=ApiResponse[dict],
)
async def skip(
    project_id: int,
    task_id: int,
    body: ApproveConfirmationRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """跳过当前阶段"""
    skip_reason = body.human_input if body else None
    success = await skip_confirmation(db, task_id, skip_reason)
    if not success:
        raise HTTPException(status_code=404, detail="No pending confirmation found")
    return ApiResponse(success=True, message="已跳过当前阶段", data={"skipped": True})


@router.post(
    "/mode",
    summary="切换运行模式",
    description="切换任务的运行模式：auto=全自动，confirm=多阶段确认",
    response_model=ApiResponse[dict],
)
async def set_mode_endpoint(
    project_id: int,
    task_id: int,
    body: SetModeRequest,
    db: AsyncSession = Depends(get_db),
):
    """设置运行模式"""
    success = await set_task_mode(db, task_id, body.mode)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or invalid mode")
    return ApiResponse(success=True, message=f"模式已切换为 {body.mode}", data={"mode": body.mode})


@router.get(
    "/chain-status",
    summary="获取链执行状态",
    description="获取当前工作流链的执行状态和进度",
    response_model=ApiResponse[ChainExecutionStatus],
)
async def get_chain_status(
    project_id: int,
    task_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取链执行状态"""
    result = await db.execute(select(AITask).where(AITask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return ApiResponse(
        success=True,
        message="ok",
        data=ChainExecutionStatus(
            task_id=task.id,
            mode=task.mode or "confirm",
            current_workflow_id=task.current_workflow_id,
            current_confirmation_point=task.current_confirmation_point,
            status=task.status or "idle",
            human_input=task.human_input,
        ),
    )


@router.get(
    "/confirmation/history",
    summary="获取确认历史",
    description="获取任务的完整确认历史记录，用于审计和追溯",
    response_model=ApiResponse[list],
)
async def get_history(
    project_id: int,
    task_id: int,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """获取确认历史"""
    history = await get_confirmation_history(db, task_id, limit)
    return ApiResponse(success=True, message="ok", data=history)
