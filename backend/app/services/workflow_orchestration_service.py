import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.ai_task import AITask, TaskStep
from app.schemas.ai_task import AITaskCreate
from app.schemas.chapter import ChapterCreate
from app.schemas.chapter_version import ChapterRevisionRequest
from app.schemas.task_runtime import TaskStatusUpdate, TaskStepStatusUpdate
from app.schemas.workflow_orchestration import AutoNovelWorkflowRequest
from app.services.chapter_consistency_task_service import execute_chapter_consistency_task
from app.services.chapter_service import create_chapter, get_chapter
from app.services.chapter_task_service import (
    execute_chapter_design_task,
    execute_chapter_generate_task,
    execute_chapter_revision_task,
)
from app.services.export_service import export_project_files
from app.services.story_graph_generation_service import generate_normalized_story_graph
from app.services.task_runtime_service import set_task_runtime_state, set_task_step_runtime_state
from app.services.task_service import create_task, create_task_step, create_task_log, list_task_steps
from app.services.trend_asset_mapping_service import map_trend_to_assets
from app.services.trend_service import execute_trend_exploration


logger = logging.getLogger(__name__)


def _summarize(value: object, limit: int = 240) -> str:
    text = str(value)
    text = " ".join(text.split())
    return text[:limit]


def _record_log(db: Session, task_id: int, step_no: int, log_type: str, message: str) -> None:
    try:
        create_task_log(db, task_id, step_no, log_type, message)
        db.commit()
    except Exception:
        pass


def _log_subagents(db: Session, task_id: int, n_agents: int, task_names: list[str]) -> None:
    """记录 SubAgent 相关的日志"""
    try:
        _record_log(db, task_id, None, "subagent", f"AI 唤起了 {n_agents} 个 SubAgent 分头执行")
        for i, task_name in enumerate(task_names, 1):
            _record_log(db, task_id, None, "subagent", f"SubAgent{i} 正在 {task_name}")
    except Exception:
        pass


def _mark_task(db: Session, task: AITask, status: str, message: str | None = None) -> None:
    task.status = status
    if status == "running":
        task.started_at = task.started_at or datetime.now(timezone.utc)
    if status == "failed":
        task.error_message = message
        task.finished_at = task.finished_at or datetime.now(timezone.utc)
    elif status == "completed":
        task.output_payload = message
        task.finished_at = task.finished_at or datetime.now(timezone.utc)
    if message:
        previous_trace = task.reasoning_trace or ""
        task.reasoning_trace = (previous_trace + "\n" + message).strip()
    db.add(task)
    db.commit()
    db.refresh(task)


def _mark_step(db: Session, step: TaskStep, status: str, message: str | None = None) -> None:
    step.status = status
    if status == "failed":
        step.error_message = message
    elif status == "completed":
        step.output_payload = message
    if status in {"completed", "failed"}:
        step.finished_at = step.finished_at or datetime.now(timezone.utc)
    elif status == "running":
        step.started_at = step.started_at or datetime.now(timezone.utc)
    db.add(step)
    db.commit()
    db.refresh(step)


def execute_auto_novel_workflow(db: Session, project_id: int, payload: AutoNovelWorkflowRequest, task_id: int | None = None) -> dict:
    if task_id:
        task = db.query(AITask).filter(AITask.id == task_id, AITask.project_id == project_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found for project {project_id}")
        steps = list_task_steps(db, task.id)
    else:
        task = create_task(
            db,
            project_id,
            AITaskCreate(
                chapter_id=payload.chapter_id,
                task_type="auto_novel_workflow",
                module_type="workflow_orchestration",
                title=payload.title,
                input_payload=payload.query_text,
                plan_text="Trend -> Asset Mapping -> Chapter Design -> Draft -> Consistency Check -> Revision",
                status="running",
            ),
        )

    step_specs = [
        (1, "Trend Exploration", "trend_exploration", "act", "Search and scrape trend signals"),
        (2, "Asset Mapping", "asset_mapping", "extract", "Map trend results into plot, characters, worldbook"),
        (3, "Story Graph Generation", "story_graph", "reason", "AI analyzes assets to generate normalized story graph"),
        (4, "Chapter Preparation", "chapter_setup", "plan", "Load or create chapter"),
        (5, "Chapter Design", "chapter_design", "reason", "Build chapter design brief and beats"),
        (6, "Chapter Draft", "chapter_generation", "act", "Generate chapter draft"),
        (7, "Consistency Check", "consistency_check", "observe", "Check consistency against assets"),
        (8, "Revision", "revision", "act", "Rewrite chapter using consistency report"),
        (9, "Export Files", "export_files", "file", "Export chapters, assets, graph and workflow logs"),
    ]

    if not task_id:
        steps = []
        for step_no, step_name, step_type, react_state, input_payload in step_specs:
            steps.append(
                create_task_step(
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
            )

    def start_step(step_no: int, message: str) -> None:
        step = next(item for item in steps if item.step_no == step_no)
        _mark_step(db, step, "running")
        logger.info(
            "Workflow step %s started: name=%s, input_summary=%s",
            step_no,
            step.step_name,
            _summarize(message),
        )
        _record_log(db, task.id, step_no, "think", f"AI 正在思考：{step.step_name}")
        _record_log(db, task.id, step_no, "act", f"AI 正在调用 {step.step_type} 模块")
        set_task_step_runtime_state(
            project_id,
            task.id,
            TaskStepStatusUpdate(
                step_no=step.step_no,
                step_name=step.step_name,
                status="running",
                react_state=step.react_state,
                message=message,
            ),
        )
        set_task_runtime_state(
            project_id,
            task.id,
            TaskStatusUpdate(status="running", current_step=step.step_type, message=message),
        )

    def complete_step(step_no: int, message: str, elapsed: float, next_step_name: str | None = None) -> None:
        step = next(item for item in steps if item.step_no == step_no)
        _mark_step(db, step, "completed", message)
        logger.info(
            "Workflow step %s completed: name=%s, elapsed=%.2fs, output_summary=%s",
            step_no,
            step.step_name,
            elapsed,
            _summarize(message),
        )
        _record_log(db, task.id, step_no, "observe", f"{step.step_name} 完成：{_summarize(message)}")
        set_task_step_runtime_state(
            project_id,
            task.id,
            TaskStepStatusUpdate(
                step_no=step.step_no,
                step_name=step.step_name,
                status="completed",
                react_state=step.react_state,
                message=f"{message} (耗时 {elapsed:.2f}s)",
            ),
        )
        if next_step_name:
            set_task_runtime_state(
                project_id,
                task.id,
                TaskStatusUpdate(status="running", current_step=next_step_name, message=message),
            )
        else:
            _mark_task(db, task, "completed", message)
            set_task_runtime_state(
                project_id,
                task.id,
                TaskStatusUpdate(status="completed", current_step="finished", message=message),
            )

    def fail_step(step_no: int, message: str, elapsed: float) -> None:
        step = next(item for item in steps if item.step_no == step_no)
        _mark_step(db, step, "failed", message)
        logger.error(
            "Workflow step %s failed: name=%s, elapsed=%.2fs, error=%s",
            step_no,
            step.step_name,
            elapsed,
            message,
        )
        set_task_step_runtime_state(
            project_id,
            task.id,
            TaskStepStatusUpdate(
                step_no=step.step_no,
                step_name=step.step_name,
                status="failed",
                react_state=step.react_state,
                message=f"{message} (耗时 {elapsed:.2f}s)",
            ),
        )

    def run_step(
        step_no: int,
        input_summary: str,
        operation: Callable[[], object],
        output_summary: Callable[[object], str],
        next_step_name: str | None = None,
        retries: int = 3,
    ) -> object:
        start_step(step_no, input_summary)
        started_at = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                if attempt > 1:
                    logger.warning("Workflow step %s retrying: attempt=%s", step_no, attempt)
                    time.sleep(min(4.0, 0.8 * (2 ** (attempt - 2))))
                result = operation()
                complete_step(step_no, output_summary(result), time.perf_counter() - started_at, next_step_name)
                return result
            except Exception as exc:
                last_error = exc
                logger.error(
                    "Workflow step %s attempt %s failed: %s",
                    step_no,
                    attempt,
                    exc,
                    exc_info=True,
                )
        elapsed = time.perf_counter() - started_at
        error_message = str(last_error or "未知错误")[:500]
        fail_step(step_no, error_message, elapsed)
        raise RuntimeError(error_message) from last_error

    set_task_runtime_state(
        project_id,
        task.id,
        TaskStatusUpdate(status="running", current_step="trend_exploration", message="Auto novel workflow started"),
    )
    _mark_task(db, task, "running", "Auto novel workflow started")

    current_step_no = 1

    try:
        _record_log(db, task.id, 1, "think", "AI 正在思考确定小说主题和题材方向...")
        _record_log(db, task.id, 1, "act", "AI 正在调用网络搜索工具进行题材趋势探索")
        trend = run_step(
            1,
            f"query={payload.query_text}, scope={payload.source_scope}, max_results={payload.max_results}",
            lambda: execute_trend_exploration(
                db,
                project_id=project_id,
                title=payload.title,
                query_text=payload.query_text,
                source_scope=payload.source_scope,
                search_depth=payload.search_depth,
                max_results=payload.max_results,
            ),
            lambda result: f"trend {result.id} collected, tags={_summarize(result.extracted_tags)}",
            "asset_mapping",
        )
        _record_log(db, task.id, 1, "tool_call", f"Tavily 搜索工具已被调用（查询 {_summarize(payload.query_text)}）")
        current_step_no = 2

        _record_log(db, task.id, 2, "think", "AI 正在将趋势数据映射为情节、人物和世界观资产...")
        asset_result = run_step(
            2,
            f"trend_id={trend.id}",
            lambda: map_trend_to_assets(
                db,
                project_id=project_id,
                trend_id=trend.id,
                create_plot_lines=True,
                create_character_candidates=True,
                create_worldbook_entries=True,
            ),
            lambda result: (
                f"assets mapped: plots={len(result['plot_lines'])}, "
                f"characters={len(result['characters'])}, "
                f"worldbook={len(result['worldbook_entries'])}"
            ),
            "chapter_preparation",
        )
        _record_log(db, task.id, 2, "observe", f"资产映射完成：情节线{len(asset_result['plot_lines'])}条，角色{len(asset_result['characters'])}个")
        plot_line_id = asset_result["plot_lines"][0].id if asset_result["plot_lines"] else None
        current_step_no = 3

        _record_log(db, task.id, 3, "think", "AI 正在分析所有资产，生成规范化的故事脉络...")
        _record_log(db, task.id, 3, "act", "AI 正在调用故事脉络生成服务，构建人物关系图、情节脉络图和事件网络")
        story_graph_result = run_step(
            3,
            f"project_id={project_id}, assets={len(asset_result['characters'])} characters, {len(asset_result['plot_lines'])} plots",
            lambda: generate_normalized_story_graph(db, project_id),
            lambda result: (
                f"story graph generated: relationships +{result.get('added_relationships', 0)}, "
                f"arcs +{result.get('added_arcs', 0)}, "
                f"events +{result.get('added_events', 0)}, "
                f"themes +{result.get('added_themes', 0)}"
            ),
            "chapter_preparation",
        )
        _record_log(db, task.id, 3, "observe", f"故事脉络生成完成：关系+{story_graph_result.get('added_relationships', 0)}, 弧线+{story_graph_result.get('added_arcs', 0)}, 事件+{story_graph_result.get('added_events', 0)}")
        current_step_no = 4

        def prepare_chapter():
            chapter = get_chapter(db, project_id, payload.chapter_id) if payload.chapter_id else None
            if chapter is None:
                chapter = create_chapter(
                    db,
                    project_id,
                    ChapterCreate(
                        chapter_no=payload.chapter_no,
                        title=payload.chapter_title,
                        summary=payload.chapter_summary,
                        objective=payload.chapter_objective,
                        conflict=payload.chapter_conflict,
                        status="planned",
                        draft_content=None,
                        final_content=None,
                        word_count=0,
                        version=1,
                    ),
                )
            return chapter

        _record_log(db, task.id, 4, "think", "AI 正在准备章节结构...")
        chapter = run_step(
            4,
            f"chapter_id={payload.chapter_id}, chapter_no={payload.chapter_no}, title={payload.chapter_title}",
            prepare_chapter,
            lambda result: f"chapter prepared: {result.id}, title={result.title}",
            "chapter_design",
        )
        current_step_no = 5

        _record_log(db, task.id, 5, "think", "AI 正在构思人物和情节设计...")
        _record_log(db, task.id, 5, "act", "AI 正在调用 LLM 生成章节大纲和节拍")
        design_result = run_step(
            5,
            f"chapter_id={chapter.id}, plot_line_id={plot_line_id}, guidance={payload.design_guidance}",
            lambda: execute_chapter_design_task(
                db,
                project_id=project_id,
                chapter_id=chapter.id,
                plot_line_id=plot_line_id,
                guidance=payload.design_guidance,
            ),
            lambda result: f"chapter plan created: {result['plan'].id}, model={result.get('model')}",
            "chapter_draft",
        )
        current_step_no = 6

        _record_log(db, task.id, 6, "think", "AI 正在书写章节草稿...")
        _record_log(db, task.id, 6, "act", "AI 正在调用生成模块撰写正文")
        draft_result = run_step(
            6,
            f"chapter_id={chapter.id}, word_target={payload.word_target}, style={payload.style_hint}",
            lambda: execute_chapter_generate_task(
                db,
                project_id=project_id,
                chapter_id=chapter.id,
                style_hint=payload.style_hint,
                word_target=payload.word_target,
            ),
            lambda result: f"chapter drafted: {result['chapter'].id}, words={result['chapter'].word_count}",
            "consistency_check",
        )
        current_step_no = 7

        _record_log(db, task.id, 7, "think", "AI 正在检查一致性...")
        _record_log(db, task.id, 7, "act", "AI 正在调用一致性检查模块对比章节与资产库")
        consistency_result = run_step(
            7,
            f"chapter_id={chapter.id}",
            lambda: execute_chapter_consistency_task(db, project_id, chapter.id),
            lambda result: _summarize(result["report"]),
            "revision",
        )
        current_step_no = 8

        _record_log(db, task.id, 8, "think", "AI 正在根据一致性报告修订章节...")
        revision_result = run_step(
            8,
            f"chapter_id={chapter.id}, revision_focus={payload.revision_focus}",
            lambda: execute_chapter_revision_task(
                db,
                project_id=project_id,
                chapter_id=chapter.id,
                payload=ChapterRevisionRequest(
                    revision_focus=payload.revision_focus,
                    style_hint=payload.style_hint,
                    word_target=payload.word_target,
                ),
            ),
            lambda result: f"chapter revised to version {result['version'].version_no}",
            "export_files",
        )
        current_step_no = 9

        _record_log(db, task.id, 9, "act", "AI 正在导出所有文件...")
        export_result = run_step(
            9,
            f"project_id={project_id}",
            lambda: export_project_files(db, project_id),
            lambda result: f"files exported: {result['export_dir']}",
        )
        _record_log(db, task.id, 9, "observe", f"文件导出完成：{export_result['export_dir']}")
    except Exception as exc:
        error_message = str(exc)[:500]
        _mark_task(db, task, "failed", f"Workflow failed at step {current_step_no}: {error_message}")
        set_task_runtime_state(
            project_id,
            task.id,
            TaskStatusUpdate(status="failed", current_step="error", message=error_message[:300]),
        )
        raise

    return {
        "task": task,
        "trend": trend,
        "chapter": revision_result["chapter"],
        "version": revision_result["version"],
        "consistency_report": revision_result["consistency_report"],
        "consistency_model": revision_result["consistency_model"],
        "rewrite_model": revision_result["rewrite_model"],
        "entity_extraction": revision_result["entity_extraction"],
        "export": export_result,
        "plot_lines": asset_result["plot_lines"],
        "characters": asset_result["characters"],
        "worldbook_entries": asset_result["worldbook_entries"],
    }
