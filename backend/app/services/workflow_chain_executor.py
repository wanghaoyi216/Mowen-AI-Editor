"""工作流链式执行器 - 自动触发工作流链

负责 wf-01→02→03→04 的自动链式执行，包含：
- 依赖关系检查
- 确认引擎集成（confirm 模式下暂停等待用户批准）
- 指数退避失败重试（最多3次）
- 断点恢复（记录执行状态，支持从中断点恢复）
- AITask 状态实时更新
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AITask
from app.schemas.workflow_orchestration import AutoNovelWorkflowRequest
from app.services.agent_event_bus import publish_tool_error
from app.services.confirmation_engine import (
    WORKFLOW_CONFIRMATION_POINTS,
    ConfirmationResult,
    TimeoutPolicy,
    check_confirmation_point,
)
from app.services.task_runtime_service import record_tool_error

logger = logging.getLogger(__name__)


WORKFLOW_CHAIN = [
    {
        "workflow_id": "wf-01",
        "name": "热点发现与灵感生成",
        "description": "AI 自主生成搜索关键词，扫描网络热点，分析趋势",
        "auto_trigger_next": True,
    },
    {
        "workflow_id": "wf-02",
        "name": "世界观与角色构建",
        "depends_on": "wf-01",
        "description": "基于热点分析结果，构建世界观、创建角色、规划剧情",
        "auto_trigger_next": True,
    },
    {
        "workflow_id": "wf-03",
        "name": "章节大纲规划",
        "depends_on": "wf-02",
        "description": "根据角色和剧情，规划章节大纲和节拍",
        "auto_trigger_next": True,
    },
    {
        "workflow_id": "wf-04",
        "name": "章节写作执行",
        "depends_on": "wf-03",
        "description": "按大纲逐章写作，包含一致性检查和修订",
        "auto_trigger_next": False,
    },
]

MAX_RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 2.0


def _emit_tool_error_event(
    task_id: Optional[int],
    project_id: Optional[int],
    *,
    tool: str,
    error_code: str,
    remediation: str = "",
    phase: str = "",
    severity: str = "warning",
    output: Optional[dict] = None,
) -> None:
    """编排链工具错误事件统一入口（B2 任务）。

    行为：
      1. 通过 ``publish_tool_error`` 把 ``tool_error`` 事件广播到
         ``AgentEventBus``，前端 AgentChat 收到后渲染黄色 toast；
      2. 通过 ``record_tool_error`` 累加到任务的 ``tool_errors`` 列表
         （供 B3 任务在 ``TaskRuntimePanel`` 显示 ⚠️ 徽章）；
      3. 任何异常都会被 try/except 吞掉，确保不阻断主流程。

    参数：
        task_id:     关联的 AITask 主键；为 None / 0 时仅做 no-op
        project_id:  关联的 Project 主键（用于 record_tool_error）
        tool:        工具名（e.g. ``web_search`` / ``web_scrape``）
        error_code:  结构化错误码（e.g. ``MISSING_TAVILY_KEY``）
        remediation: 中文修复建议
        phase:       当前阶段标识（e.g. ``research`` / ``planner``）
        severity:    严重程度，默认 ``"warning"``（不阻断任务）
        output:      工具原始返回 dict（可选，便于调试日志）

    设计动机：把"发布 + 累计"两步封装为单一 helper，编排链代码
    复杂时只需在工具调用点（``ai_workflow_graph_service.py`` /
    ``workflow_orchestration_service.py``）调用本函数即可，无需关心
    bus / record_tool_error 的细节。
    """
    if not task_id or not error_code:
        return
    try:
        publish_tool_error(
            task_id=task_id,
            phase=phase or None,
            tool=tool,
            error_code=error_code,
            remediation=remediation,
            severity=severity,
        )
    except Exception as exc:  # noqa: BLE001 - 事件总线失败不能影响主流程
        logger.debug(
            "_emit_tool_error_event publish failed: task_id=%s, tool=%s, err=%s",
            task_id, tool, exc,
        )
    try:
        if project_id:
            record_tool_error(
                project_id=project_id,
                task_id=task_id,
                tool=tool,
                error_code=error_code,
                remediation=remediation,
                phase=phase,
                severity=severity,
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "_emit_tool_error_event record failed: task_id=%s, tool=%s, err=%s",
            task_id, tool, exc,
        )
    if output is not None:
        try:
            logger.info(
                "tool_error event: task_id=%s, tool=%s, error_code=%s, mode=%s",
                task_id, tool, error_code, output.get("mode"),
            )
        except Exception:
            pass


def detect_tool_error(output: Any) -> Optional[dict]:
    """检查工具返回值是否携带结构化 error_code。

    B1 在 ``web_search_tool`` / ``web_scrape_tool`` 已经约定：当工具
    因 key 缺失而跳过时返回 ``{"error_code": "...", "remediation": "..."}``。
    本函数在编排链的工具调用点统一探测该结构。

    返回 ``None``（无错误）或 ``{"tool_name", "error_code", "remediation", "phase"}``
    字典（便于调用方直接透传给 ``_emit_tool_error_event``）。
    """
    if not isinstance(output, dict):
        return None
    error_code = output.get("error_code")
    if not error_code or not isinstance(error_code, str):
        return None
    remediation = output.get("remediation")
    if not isinstance(remediation, str):
        remediation = ""
    tool_name = output.get("tool") or output.get("name") or ""
    severity = output.get("severity") or "warning"
    if severity not in {"warning", "error"}:
        severity = "warning"
    return {
        "tool_name": str(tool_name),
        "error_code": str(error_code),
        "remediation": remediation,
        "severity": str(severity),
    }


@dataclass
class WorkflowResult:
    workflow_id: str
    name: str
    status: str
    duration: float
    output_context: dict = field(default_factory=dict)
    error: Optional[str] = None
    attempts: int = 1


@dataclass
class ChainExecutionResult:
    workflow_results: list[WorkflowResult]
    total_duration: float
    status: str
    task_id: Optional[int] = None
    resumed_from: Optional[int] = None


def _build_chain_state(completed_results: list[WorkflowResult], current_position: int, error: Optional[str] = None) -> dict:
    """构建链执行状态快照，用于断点恢复"""
    return {
        "chain_position": current_position,
        "completed_workflows": [
            {
                "workflow_id": r.workflow_id,
                "status": r.status,
                "output_context": r.output_context,
            }
            for r in completed_results
        ],
        "error": error,
    }


async def _load_chain_state(task: AITask) -> tuple[int, list[WorkflowResult]]:
    """
    从 AITask 加载链执行状态
    
    Returns:
        (resume_position, completed_results)
    """
    if not task.output_payload:
        return 0, []

    try:
        state = json.loads(task.output_payload)
        position = state.get("chain_position", 0)
        completed = []
        for item in state.get("completed_workflows", []):
            completed.append(WorkflowResult(
                workflow_id=item["workflow_id"],
                name=item.get("name", ""),
                status=item.get("status", "completed"),
                duration=item.get("duration", 0),
                output_context=item.get("output_context", {}),
            ))
        return position, completed
    except (json.JSONDecodeError, KeyError, TypeError):
        return 0, []


async def _save_chain_state(
    db: AsyncSession,
    task_id: int,
    completed_results: list[WorkflowResult],
    current_position: int,
    error: Optional[str] = None,
) -> None:
    """保存链执行状态到 AITask.output_payload"""
    state = _build_chain_state(completed_results, current_position, error)
    await db.execute(
        update(AITask)
        .where(AITask.id == task_id)
        .values(output_payload=json.dumps(state, ensure_ascii=False))
    )
    await db.commit()


async def _update_task_workflow_state(
    db: AsyncSession,
    task_id: int,
    workflow_id: Optional[str] = None,
    confirmation_point: Optional[str] = None,
    status: Optional[str] = None,
    human_input: Optional[str] = None,
) -> None:
    """更新 AITask 的工作流相关状态字段"""
    values = {}
    if workflow_id is not None:
        values["current_workflow_id"] = workflow_id
    if confirmation_point is not None:
        values["current_confirmation_point"] = confirmation_point
    if status is not None:
        values["status"] = status
    if human_input is not None:
        values["human_input"] = human_input

    if values:
        await db.execute(update(AITask).where(AITask.id == task_id).values(**values))
        await db.commit()


async def _execute_single_workflow(
    db: AsyncSession,
    project_id: int,
    wf_id: str,
    wf_def: dict,
    context: dict,
) -> WorkflowResult:
    """
    执行单个工作流，带指数退避重试
    
    由于 execute_auto_novel_workflow 是同步函数，通过 run_sync 在线程池中执行。
    """
    from app.services.workflow_orchestration_service import execute_auto_novel_workflow

    wf_name = wf_def["name"]
    last_error = None

    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        try:
            logger.info("执行工作流 %s (%s), 尝试 %d/%d", wf_id, wf_name, attempt, MAX_RETRY_ATTEMPTS)

            payload = AutoNovelWorkflowRequest(
                title=context.get("title", wf_name),
                query_text=context.get("query_text", context.get("title", wf_name)),
                source_scope=context.get("source_scope", "web"),
                search_depth=context.get("search_depth", "advanced"),
                max_results=context.get("max_results", 5),
                chapter_id=context.get("chapter_id"),
                chapter_no=context.get("chapter_no", 1),
                chapter_title=context.get("chapter_title", "自动生成章节"),
                chapter_summary=context.get("chapter_summary"),
                chapter_objective=context.get("chapter_objective"),
                chapter_conflict=context.get("chapter_conflict"),
                design_guidance=context.get("design_guidance"),
                style_hint=context.get("style_hint"),
                revision_focus=context.get("revision_focus"),
                word_target=context.get("word_target", 1800),
            )

            result = await db.run_sync(
                lambda sync_db: execute_auto_novel_workflow(sync_db, project_id, payload)
            )

            output_context = {}
            task_obj = result.get("task")
            if task_obj:
                output_context["task_id"] = task_obj.id
            if result.get("trend"):
                output_context["trend_id"] = result["trend"].id
            if result.get("chapter"):
                output_context["chapter_id"] = result["chapter"].id
                output_context["chapter"] = result["chapter"]
            output_context["plot_lines"] = result.get("plot_lines", [])
            output_context["characters"] = result.get("characters", [])
            output_context["worldbook_entries"] = result.get("worldbook_entries", [])

            return WorkflowResult(
                workflow_id=wf_id,
                name=wf_name,
                status="completed",
                duration=0,
                output_context=output_context,
                attempts=attempt,
            )

        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "工作流 %s 执行失败 (尝试 %d/%d): %s",
                wf_id, attempt, MAX_RETRY_ATTEMPTS, last_error[:200],
            )

            if attempt < MAX_RETRY_ATTEMPTS:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.info("等待 %.1f 秒后重试...", delay)
                await asyncio.sleep(delay)

    return WorkflowResult(
        workflow_id=wf_id,
        name=wf_name,
        status="failed",
        duration=0,
        output_context={"error": last_error},
        error=last_error,
        attempts=MAX_RETRY_ATTEMPTS,
    )


async def execute_workflow_chain(
    db: AsyncSession,
    project_id: int,
    task_id: int,
    initial_params: Optional[dict] = None,
) -> ChainExecutionResult:
    """
    按链顺序自动触发工作流 wf-01→02→03→04
    
    功能：
    - 断点恢复：从 AITask.output_payload 读取上次执行状态
    - 确认引擎集成：confirm 模式下每个工作流完成后暂停等待用户批准
    - 失败重试：指数退避重试最多3次
    - 状态更新：实时更新 AITask 的 current_workflow_id、current_confirmation_point 等
    
    Args:
        db: 异步数据库会话
        project_id: 项目 ID
        task_id: AITask ID（用于跟踪链执行状态）
        initial_params: 初始参数（title、query_text 等）
    
    Returns:
        ChainExecutionResult 包含所有工作流的执行结果
    """
    task_result = await db.execute(select(AITask).where(AITask.id == task_id))
    task = task_result.scalar_one_or_none()
    if not task:
        return ChainExecutionResult(
            workflow_results=[],
            total_duration=0,
            status="failed",
        )

    mode = task.mode or "confirm"
    context = initial_params or {}

    resume_position, completed_results = await _load_chain_state(task)
    resumed_from = resume_position if resume_position > 0 else None

    if resumed_from:
        logger.info("从断点恢复：跳过前 %d 个工作流", resumed_from)
        for r in completed_results:
            ctx = r.output_context or {}
            if "chapter" in ctx:
                del ctx["chapter"]
            context.update(ctx)

    start_time = time.time()

    for idx, wf_def in enumerate(WORKFLOW_CHAIN):
        wf_id = wf_def["workflow_id"]

        if idx < resume_position:
            continue

        logger.info("开始执行工作流 %d/%d: %s", idx + 1, len(WORKFLOW_CHAIN), wf_id)

        await _update_task_workflow_state(
            db, task_id,
            workflow_id=wf_id,
            confirmation_point=None,
            status="running",
        )

        result = await _execute_single_workflow(db, project_id, wf_id, wf_def, context)
        result.duration = time.time() - start_time

        if result.status == "completed":
            wf_context = result.output_context.copy()
            if "chapter" in wf_context:
                del wf_context["chapter"]
            context.update(wf_context)

            completed_results.append(result)
            await _save_chain_state(db, task_id, completed_results, idx + 1)

            if mode == "confirm" and wf_def.get("auto_trigger_next"):
                confirmation_points = WORKFLOW_CONFIRMATION_POINTS.get(wf_id, {})
                if confirmation_points:
                    last_point = list(confirmation_points.keys())[-1]

                    await _update_task_workflow_state(
                        db, task_id,
                        confirmation_point=last_point,
                        status="waiting_confirmation",
                    )

                    confirmation_result: ConfirmationResult = await check_confirmation_point(
                        db=db,
                        task_id=task_id,
                        workflow_id=wf_id,
                        point_id=last_point,
                        mode=mode,
                        summary={
                            "workflow_id": wf_id,
                            "workflow_name": wf_def["name"],
                            "status": "completed",
                            "output_keys": list(result.output_context.keys()),
                        },
                        timeout_policy=TimeoutPolicy.SKIP,
                    )

                    if not confirmation_result.approved:
                        logger.info("工作流 %s 被用户跳过确认: %s", wf_id, confirmation_result.reason)

                    await _update_task_workflow_state(
                        db, task_id,
                        confirmation_point=None,
                        status="running",
                        human_input=confirmation_result.human_input,
                    )

            if not wf_def.get("auto_trigger_next"):
                logger.info("工作流 %s 不自动触发下一个，链执行结束", wf_id)
                break

        elif result.status == "failed":
            completed_results.append(result)
            await _save_chain_state(
                db, task_id, completed_results, idx,
                error=result.error,
            )
            await _update_task_workflow_state(
                db, task_id,
                status="failed",
            )
            break

    total_duration = time.time() - start_time
    all_completed = all(r.status == "completed" for r in completed_results)

    if all_completed and completed_results:
        final_status = "completed"
        await _update_task_workflow_state(
            db, task_id,
            workflow_id=None,
            confirmation_point=None,
            status="completed",
        )
    elif completed_results:
        final_status = "partial"
    else:
        final_status = "failed"

    await _save_chain_state(db, task_id, completed_results, len(completed_results))

    return ChainExecutionResult(
        workflow_results=completed_results,
        total_duration=total_duration,
        status=final_status,
        task_id=task_id,
        resumed_from=resumed_from,
    )
