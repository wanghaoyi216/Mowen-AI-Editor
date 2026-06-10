"""阶段确认引擎 - Human-in-the-Loop 确认点控制"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConfirmationRequest, AITask

logger = logging.getLogger(__name__)


# ============================================================================
# 工作流确认点定义
# ============================================================================

WORKFLOW_CONFIRMATION_POINTS: Dict[str, Dict[str, str]] = {
    "wf-01": {
        "after_search": "热点扫描完成，是否确认搜索结果？",
        "after_analysis": "趋势分析完成，是否确认分析结论？",
    },
    "wf-02": {
        "after_worldbuilding": "世界观构建完成，是否确认世界观条目？",
        "after_characters": "角色创建完成，是否确认角色档案？",
        "after_plots": "剧情规划完成，是否确认剧情线？",
    },
    "wf-03": {
        "after_outline": "章节大纲规划完成，是否确认大纲？",
    },
    "wf-04": {
        "after_draft": "章节草稿生成完成，是否确认内容？",
        "after_revision": "章节修订完成，是否确认最终版本？",
    },
}


# ============================================================================
# 超时策略枚举
# ============================================================================

class TimeoutPolicy(str, Enum):
    """超时后的处理策略"""
    SKIP = "skip"       # 超时后自动跳过
    FAIL = "fail"       # 超时后标记为失败


# ============================================================================
# 确认结果数据类
# ============================================================================

class ConfirmationResult:
    """确认操作的结果"""
    
    def __init__(
        self,
        approved: bool,
        skip: bool = False,
        human_input: str | None = None,
        reason: str | None = None,
    ):
        self.approved = approved
        self.skip = skip
        self.human_input = human_input
        self.reason = reason or ""
    
    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "skip": self.skip,
            "human_input": self.human_input,
            "reason": self.reason,
        }
    
    @classmethod
    def auto_pass(cls) -> ConfirmationResult:
        return cls(approved=True, skip=False, reason="auto_mode")
    
    @classmethod
    def timeout_skip(cls) -> ConfirmationResult:
        return cls(approved=False, skip=True, reason="超时自动跳过")
    
    @classmethod
    def timeout_fail(cls) -> ConfirmationResult:
        return cls(approved=False, skip=False, reason="确认超时，任务终止")


# ============================================================================
# 确认点创建
# ============================================================================

async def create_confirmation_point(
    db: AsyncSession,
    task_id: int,
    workflow_id: str,
    point_id: str,
    summary: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> ConfirmationRequest:
    """
    创建确认点并记录完整上下文
    
    Args:
        db: 异步数据库会话
        task_id: AI 任务 ID
        workflow_id: 工作流 ID（如 wf-01）
        point_id: 确认点 ID（如 after_search）
        summary: 阶段成果摘要
        context: 额外上下文信息（前置阶段输出、执行参数等）
    
    Returns:
        创建的 ConfirmationRequest 对象
    """
    message = WORKFLOW_CONFIRMATION_POINTS.get(workflow_id, {}).get(
        point_id, "请确认当前阶段成果"
    )
    
    merged_summary = summary or {}
    if context:
        merged_summary["_context"] = context
    
    confirmation = ConfirmationRequest(
        task_id=task_id,
        workflow_id=workflow_id,
        point_id=point_id,
        message=message,
        summary=merged_summary,
        status="pending",
        human_input=None,
    )
    
    db.add(confirmation)
    await db.flush()
    
    # 更新任务状态为等待确认
    await _update_task_waiting(db, task_id, point_id)
    await db.commit()
    
    logger.info(
        "创建确认点: task_id=%s, workflow_id=%s, point_id=%s",
        task_id, workflow_id, point_id,
    )
    
    return confirmation


async def _update_task_waiting(
    db: AsyncSession,
    task_id: int,
    point_id: str,
) -> None:
    """更新任务状态为等待确认"""
    result = await db.execute(select(AITask).where(AITask.id == task_id))
    task = result.scalar_one_or_none()
    if task:
        task.status = "waiting_confirmation"
        task.current_confirmation_point = point_id


# ============================================================================
# 运行模式管理
# ============================================================================

async def get_task_mode(db: AsyncSession, task_id: int) -> str:
    """
    获取任务的运行模式
    
    Returns:
        "auto" 或 "confirm"
    """
    result = await db.execute(select(AITask).where(AITask.id == task_id))
    task = result.scalar_one_or_none()
    if task and task.mode:
        return task.mode
    return "confirm"


async def set_task_mode(
    db: AsyncSession,
    task_id: int,
    mode: str,
) -> bool:
    """
    动态切换任务运行模式
    
    Args:
        mode: "auto" 或 "confirm"
    
    Returns:
        是否成功切换
    """
    if mode not in ("auto", "confirm"):
        logger.warning("无效的运行模式: %s", mode)
        return False
    
    result = await db.execute(select(AITask).where(AITask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        return False
    
    task.mode = mode
    await db.commit()
    
    logger.info("任务 %s 运行模式切换为: %s", task_id, mode)
    return True


# ============================================================================
# 确认点检查（核心入口）
# ============================================================================

async def check_confirmation_point(
    db: AsyncSession,
    task_id: int,
    workflow_id: str,
    point_id: str,
    mode: str | None = None,
    summary: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    timeout: int = 3600,
    timeout_policy: TimeoutPolicy = TimeoutPolicy.SKIP,
) -> ConfirmationResult:
    """
    检查确认点，根据运行模式决定是否等待用户确认
    
    Args:
        db: 异步数据库会话
        task_id: AI 任务 ID
        workflow_id: 工作流 ID
        point_id: 确认点 ID
        mode: 运行模式，若为 None 则从任务读取
        summary: 阶段成果摘要
        context: 额外上下文
        timeout: 超时时间（秒），默认 3600 秒（1小时）
        timeout_policy: 超时策略
    
    Returns:
        ConfirmationResult 对象
    """
    # 确定运行模式
    if mode is None:
        mode = await get_task_mode(db, task_id)
    
    # auto 模式直接通过
    if mode == "auto":
        return ConfirmationResult.auto_pass()
    
    # confirm 模式：创建确认点并等待
    confirmation = await create_confirmation_point(
        db, task_id, workflow_id, point_id, summary, context,
    )
    
    return await _wait_for_confirmation(
        db,
        confirmation.id,
        timeout=timeout,
        timeout_policy=timeout_policy,
    )


# ============================================================================
# 等待确认（轮询）
# ============================================================================

async def _wait_for_confirmation(
    db: AsyncSession,
    confirmation_id: int,
    timeout: int = 3600,
    timeout_policy: TimeoutPolicy = TimeoutPolicy.SKIP,
) -> ConfirmationResult:
    """
    等待用户确认（通过轮询数据库状态）
    
    Args:
        db: 异步数据库会话
        confirmation_id: 确认请求 ID
        timeout: 超时时间（秒）
        timeout_policy: 超时策略
    
    Returns:
        ConfirmationResult 对象
    """
    start = time.monotonic()
    poll_interval = 2.0  # 轮询间隔 2 秒
    
    while time.monotonic() - start < timeout:
        result = await db.execute(
            select(ConfirmationRequest).where(
                ConfirmationRequest.id == confirmation_id
            )
        )
        confirmation = result.scalar_one_or_none()
        
        if confirmation and confirmation.status != "pending":
            return _build_result_from_confirmation(confirmation)
        
        await asyncio.sleep(poll_interval)
    
    # 超时处理
    logger.warning(
        "确认超时: confirmation_id=%s, policy=%s",
        confirmation_id, timeout_policy,
    )
    
    if timeout_policy == TimeoutPolicy.FAIL:
        return ConfirmationResult.timeout_fail()
    
    # 默认跳过策略
    await _auto_skip_on_timeout(db, confirmation_id)
    return ConfirmationResult.timeout_skip()


async def _auto_skip_on_timeout(
    db: AsyncSession,
    confirmation_id: int,
) -> None:
    """超时后自动跳过确认点"""
    result = await db.execute(
        select(ConfirmationRequest).where(
            ConfirmationRequest.id == confirmation_id
        )
    )
    confirmation = result.scalar_one_or_none()
    if confirmation and confirmation.status == "pending":
        confirmation.status = "skipped"
        confirmation.human_input = "超时自动跳过"
        
        task_result = await db.execute(
            select(AITask).where(AITask.id == confirmation.task_id)
        )
        task = task_result.scalar_one_or_none()
        if task:
            task.status = "running"
            task.current_confirmation_point = None
        
        await db.commit()


def _build_result_from_confirmation(
    confirmation: ConfirmationRequest,
) -> ConfirmationResult:
    """从 ConfirmationRequest 构建 ConfirmationResult"""
    if confirmation.status == "approved":
        return ConfirmationResult(
            approved=True,
            skip=False,
            human_input=confirmation.human_input,
            reason="用户批准",
        )
    elif confirmation.status == "skipped":
        return ConfirmationResult(
            approved=False,
            skip=True,
            human_input=confirmation.human_input,
            reason=confirmation.human_input or "用户跳过",
        )
    else:
        return ConfirmationResult(
            approved=False,
            skip=False,
            reason=f"未知状态: {confirmation.status}",
        )


# ============================================================================
# 批准确认
# ============================================================================

async def approve_confirmation(
    db: AsyncSession,
    task_id: int,
    human_input: str | None = None,
) -> bool:
    """
    确认并继续，支持用户输入修改建议
    
    Args:
        db: 异步数据库会话
        task_id: AI 任务 ID
        human_input: 用户输入的补充建议或修改意见
    
    Returns:
        是否成功批准
    """
    result = await db.execute(
        select(ConfirmationRequest)
        .where(ConfirmationRequest.task_id == task_id)
        .where(ConfirmationRequest.status == "pending")
        .order_by(desc(ConfirmationRequest.created_at))
        .limit(1)
    )
    confirmation = result.scalar_one_or_none()
    
    if not confirmation:
        logger.warning("未找到待确认记录: task_id=%s", task_id)
        return False
    
    confirmation.status = "approved"
    confirmation.approved_at = datetime.now(timezone.utc)
    confirmation.human_input = human_input
    
    # 更新任务状态
    task_result = await db.execute(select(AITask).where(AITask.id == task_id))
    task = task_result.scalar_one_or_none()
    if task:
        task.status = "running"
        task.current_confirmation_point = None
        task.human_input = human_input
    
    await db.commit()
    
    logger.info(
        "确认已批准: task_id=%s, human_input=%s",
        task_id, human_input[:50] if human_input else None,
    )
    
    return True


# ============================================================================
# 跳过确认
# ============================================================================

async def skip_confirmation(
    db: AsyncSession,
    task_id: int,
    skip_reason: str | None = None,
) -> bool:
    """
    跳过当前阶段
    
    Args:
        db: 异步数据库会话
        task_id: AI 任务 ID
        skip_reason: 跳过原因说明
    
    Returns:
        是否成功跳过
    """
    result = await db.execute(
        select(ConfirmationRequest)
        .where(ConfirmationRequest.task_id == task_id)
        .where(ConfirmationRequest.status == "pending")
        .order_by(desc(ConfirmationRequest.created_at))
        .limit(1)
    )
    confirmation = result.scalar_one_or_none()
    
    if not confirmation:
        logger.warning("未找到待确认记录: task_id=%s", task_id)
        return False
    
    confirmation.status = "skipped"
    confirmation.human_input = skip_reason or "用户手动跳过"
    
    # 更新任务状态
    task_result = await db.execute(select(AITask).where(AITask.id == task_id))
    task = task_result.scalar_one_or_none()
    if task:
        task.status = "running"
        task.current_confirmation_point = None
    
    await db.commit()
    
    logger.info(
        "确认已跳过: task_id=%s, reason=%s",
        task_id, skip_reason or "用户手动跳过",
    )
    
    return True


# ============================================================================
# 获取待确认信息
# ============================================================================

async def get_pending_confirmation(
    db: AsyncSession,
    task_id: int,
) -> dict[str, Any] | None:
    """
    获取当前等待确认的信息
    
    Args:
        db: 异步数据库会话
        task_id: AI 任务 ID
    
    Returns:
        待确认信息字典，若无待确认则返回 None
    """
    result = await db.execute(
        select(ConfirmationRequest)
        .where(ConfirmationRequest.task_id == task_id)
        .where(ConfirmationRequest.status == "pending")
        .order_by(desc(ConfirmationRequest.created_at))
        .limit(1)
    )
    confirmation = result.scalar_one_or_none()
    
    if not confirmation:
        return None
    
    return {
        "task_id": confirmation.task_id,
        "workflow_id": confirmation.workflow_id,
        "point_id": confirmation.point_id,
        "message": confirmation.message,
        "summary": confirmation.summary,
        "created_at": confirmation.created_at,
    }


# ============================================================================
# 确认历史追踪
# ============================================================================

async def get_confirmation_history(
    db: AsyncSession,
    task_id: int,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    查询任务的完整确认历史
    
    Args:
        db: 异步数据库会话
        task_id: AI 任务 ID
        limit: 返回记录数上限
    
    Returns:
        确认历史记录列表，按创建时间倒序
    """
    result = await db.execute(
        select(ConfirmationRequest)
        .where(ConfirmationRequest.task_id == task_id)
        .order_by(desc(ConfirmationRequest.created_at))
        .limit(limit)
    )
    confirmations = result.scalars().all()
    
    return [
        {
            "id": c.id,
            "workflow_id": c.workflow_id,
            "point_id": c.point_id,
            "message": c.message,
            "summary": c.summary,
            "status": c.status,
            "human_input": c.human_input,
            "approved_at": c.approved_at,
            "created_at": c.created_at,
        }
        for c in confirmations
    ]


async def get_confirmation_history_by_workflow(
    db: AsyncSession,
    task_id: int,
    workflow_id: str,
) -> list[dict[str, Any]]:
    """
    查询指定工作流的确认历史
    
    Args:
        db: 异步数据库会话
        task_id: AI 任务 ID
        workflow_id: 工作流 ID
    
    Returns:
        确认历史记录列表
    """
    result = await db.execute(
        select(ConfirmationRequest)
        .where(ConfirmationRequest.task_id == task_id)
        .where(ConfirmationRequest.workflow_id == workflow_id)
        .order_by(desc(ConfirmationRequest.created_at))
    )
    confirmations = result.scalars().all()
    
    return [
        {
            "id": c.id,
            "point_id": c.point_id,
            "message": c.message,
            "summary": c.summary,
            "status": c.status,
            "human_input": c.human_input,
            "approved_at": c.approved_at,
            "created_at": c.created_at,
        }
        for c in confirmations
    ]


# ============================================================================
# 批量操作辅助
# ============================================================================

async def batch_approve_all_pending(
    db: AsyncSession,
    task_id: int,
    human_input: str | None = None,
) -> int:
    """
    批量批准任务的所有待确认点
    
    Args:
        db: 异步数据库会话
        task_id: AI 任务 ID
        human_input: 用户输入建议
    
    Returns:
        成功批准的确认点数量
    """
    result = await db.execute(
        select(ConfirmationRequest)
        .where(ConfirmationRequest.task_id == task_id)
        .where(ConfirmationRequest.status == "pending")
    )
    pending = result.scalars().all()
    
    count = 0
    for confirmation in pending:
        confirmation.status = "approved"
        confirmation.approved_at = datetime.now(timezone.utc)
        confirmation.human_input = human_input
        count += 1
    
    if count > 0:
        task_result = await db.execute(select(AITask).where(AITask.id == task_id))
        task = task_result.scalar_one_or_none()
        if task:
            task.status = "running"
            task.current_confirmation_point = None
            task.human_input = human_input
        
        await db.commit()
    
    return count


# ============================================================================
# 工作流阶段集成辅助
# ============================================================================

async def check_workflow_stage_completion(
    db: AsyncSession,
    task_id: int,
    workflow_id: str,
    stage_output: dict[str, Any],
    mode: str | None = None,
    timeout: int = 3600,
    timeout_policy: TimeoutPolicy = TimeoutPolicy.SKIP,
) -> ConfirmationResult:
    """
    在工作流阶段完成后调用确认点检查
    
    该函数封装了工作流执行器在每个阶段完成后调用的完整逻辑：
    1. 确定该工作流的最后一个确认点
    2. 创建确认点，附带阶段输出摘要
    3. 根据运行模式决定是否等待用户确认
    4. 返回确认结果供执行器决定是否继续下一阶段
    
    Args:
        db: 异步数据库会话
        task_id: AI 任务 ID
        workflow_id: 工作流 ID（如 wf-01）
        stage_output: 阶段输出数据（将作为 summary 和 context）
        mode: 运行模式，若为 None 则从任务读取
        timeout: 超时时间（秒）
        timeout_policy: 超时策略
    
    Returns:
        ConfirmationResult 对象
            - approved=True: 用户批准，可继续下一阶段
            - approved=False, skip=True: 用户跳过，可继续下一阶段
            - approved=False, skip=False: 确认失败（超时策略为 fail），应终止链执行
    
    Example:
        ```python
        result = await check_workflow_stage_completion(
            db, task_id, "wf-02",
            {"characters": [...], "worldbook": [...]},
        )
        if not result.approved and not result.skip:
            # 确认失败，终止执行
            raise WorkflowAborted(result.reason)
        # 继续下一阶段
        ```
    """
    # 获取该工作流的最后一个确认点作为代表
    points = WORKFLOW_CONFIRMATION_POINTS.get(workflow_id, {})
    if not points:
        # 如果没有定义确认点，直接通过
        return ConfirmationResult.auto_pass()
    
    last_point = list(points.keys())[-1]
    
    return await check_confirmation_point(
        db=db,
        task_id=task_id,
        workflow_id=workflow_id,
        point_id=last_point,
        mode=mode,
        summary={
            "workflow_id": workflow_id,
            "status": "completed",
            "output_keys": list(stage_output.keys()),
        },
        context=stage_output,
        timeout=timeout,
        timeout_policy=timeout_policy,
    )
