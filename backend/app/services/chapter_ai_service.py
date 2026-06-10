from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.ai_task import AITask
from app.models.chapter import Chapter
from app.models.chapter_plan import ChapterPlan
from app.models.chapter_version import ChapterVersion
from app.models.character import Character
from app.models.plot_line import PlotLine
from app.models.trend_exploration import TrendExploration
from app.models.worldbook_entry import WorldbookEntry
from app.schemas.ai_task import AITaskCreate
from app.services.graph_service import sync_chapter_plan_to_neo4j, sync_chapter_to_neo4j
from app.services.openrouter_service import extract_message_content, generate_with_openrouter
from app.services.task_service import create_task
from app.services.writing_constraints_service import (
    ProjectConstraints,
    build_constraint_block,
    build_word_budget_line,
    count_words,
    load_project_constraints,
)


logger = logging.getLogger(__name__)


# 自动触发节流：相邻 N 秒内的 story_graph_generation 任务只保留最新一个，
# 避免每写完一节都拉一遍 AI。
_STORY_GRAPH_AUTO_COOLDOWN = timedelta(seconds=120)


# 字数强制校验：草稿不足目标字数 80% 时，最多再补写几轮
_WORD_ENFORCE_MIN_RATIO = 0.8
_WORD_ENFORCE_MAX_ROUNDS = 2


def _enforce_word_target(
    content: str,
    *,
    constraints: ProjectConstraints,
    word_target: int,
    system_prompt: str,
    base_user_prompt: str,
    preferred_keywords: list[str],
) -> str:
    """若正文字数明显不足，驱动模型续写补足，最多 ``_WORD_ENFORCE_MAX_ROUNDS`` 轮。

    这是"AI 实时获取当前字数、判断该怎么写"的落地：每轮把当前字数、还差多少
    回灌给模型，要求其衔接续写而非重写，直到达到目标下限或用尽轮数。
    """
    min_acceptable = max(
        constraints.min_words_per_chapter,
        int(word_target * _WORD_ENFORCE_MIN_RATIO),
    )
    current = count_words(content)
    rounds = 0
    while current < min_acceptable and rounds < _WORD_ENFORCE_MAX_ROUNDS:
        rounds += 1
        budget_line = build_word_budget_line(
            constraints, word_target=word_target, current_words=current
        )
        continuation_prompt = (
            f"{base_user_prompt}\n\n"
            f"{budget_line}\n"
            "下面是已经写好的正文，请**直接无缝续写后续情节**（不要重复已有内容、"
            "不要写'续：'之类的标记、不要复述前文），把本章补足到目标字数，"
            "保持同一风格、人称与时态：\n\n"
            f"{content}"
        )
        try:
            result = generate_with_openrouter(
                system_prompt=system_prompt,
                user_prompt=continuation_prompt,
                preferred_keywords=preferred_keywords,
                role="creator",
            )
        except Exception:
            break
        addition = extract_message_content(result.get("completion")).strip()
        if not addition:
            break
        # 防止模型回声/重复：续写内容若已基本包含在正文中，停止补写避免重复堆叠
        if addition in content:
            break
        content = f"{content}\n\n{addition}"
        new_total = count_words(content)
        # 续写没带来有效增量则停止，避免空转
        if new_total <= current:
            break
        current = new_total
    return content


def _collect_chapter_assets(db: Session, project_id: int, plot_line_id: int | None = None) -> dict:
    plot_lines_query = select(PlotLine).where(PlotLine.project_id == project_id).order_by(PlotLine.priority.desc())
    if plot_line_id is not None:
        plot_lines_query = plot_lines_query.where(PlotLine.id == plot_line_id)

    plot_lines = list(db.scalars(plot_lines_query.limit(4)))
    characters = list(
        db.scalars(select(Character).where(Character.project_id == project_id).order_by(Character.updated_at.desc()).limit(6))
    )
    worldbook_entries = list(
        db.scalars(
            select(WorldbookEntry).where(WorldbookEntry.project_id == project_id).order_by(WorldbookEntry.updated_at.desc()).limit(6)
        )
    )
    trends = list(
        db.scalars(
            select(TrendExploration)
            .where(TrendExploration.project_id == project_id)
            .order_by(TrendExploration.updated_at.desc())
            .limit(3)
        )
    )

    return {
        "plot_lines": plot_lines,
        "characters": characters,
        "worldbook_entries": worldbook_entries,
        "trends": trends,
    }


def _build_asset_summary(assets: dict) -> str:
    plot_lines = assets["plot_lines"]
    characters = assets["characters"]
    worldbook_entries = assets["worldbook_entries"]
    trends = assets["trends"]

    parts = [
        "Plot Lines:",
        *[
            f"- {item.title}: goal={item.goal or ''}; conflict={item.conflict or ''}"
            for item in plot_lines
        ],
        "Characters:",
        *[
            f"- {item.name}: role={item.role_type or ''}; goal={item.goal or ''}; arc={item.arc_summary or ''}"
            for item in characters
        ],
        "Worldbook:",
        *[
            f"- {item.title}: {item.content[:220]}"
            for item in worldbook_entries
        ],
        "Trend Signals:",
        *[
            f"- {item.title}: {item.query_text}"
            for item in trends
        ],
    ]
    return "\n".join(parts)


def _persist_chapter_version(
    db: Session,
    *,
    chapter: Chapter,
    content: str,
    model_id: str | None,
    operation_type: str,
    instruction: str | None = None,
    consistency_report: str | None = None,
    summary: str | None = None,
) -> ChapterVersion:
    item = ChapterVersion(
        project_id=chapter.project_id,
        chapter_id=chapter.id,
        version_no=chapter.version,
        operation_type=operation_type,
        instruction=instruction,
        consistency_report=consistency_report,
        content=content,
        summary=summary,
        selected_model=model_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def build_chapter_plan(
    db: Session,
    project_id: int,
    chapter_id: int,
    plot_line_id: int | None = None,
    guidance: str | None = None,
) -> ChapterPlan:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.project_id != project_id:
        raise ValueError("Chapter not found in project")

    assets = _collect_chapter_assets(db, project_id, plot_line_id)
    asset_summary = _build_asset_summary(assets)
    constraints = load_project_constraints(db, project_id)
    constraint_block = build_constraint_block(constraints)

    system_prompt = (
        "你是一位资深小说编辑与章节策划。请基于结构化的项目资产，产出可直接用于"
        "成稿的章节设计概要(Design Brief)与节拍表(Beat Sheet)。设计必须严格贴合"
        "给定的题材、风格、基调与字数预算。"
    )
    user_prompt = (
        f"{constraint_block}\n\n"
        f"Project assets:\n{asset_summary}\n\n"
        f"Chapter info:\n"
        f"- chapter_no: {chapter.chapter_no}\n"
        f"- title: {chapter.title}\n"
        f"- summary: {chapter.summary or ''}\n"
        f"- objective: {chapter.objective or ''}\n"
        f"- conflict: {chapter.conflict or ''}\n"
        f"- extra_guidance: {guidance or ''}\n\n"
        "请输出两个清晰小节（用中文）：\n"
        "1. Design Brief（设计概要：本章目标、视角、情绪曲线、与主线关系）\n"
        "2. Beat Sheet（节拍表：按场景列出冲突、转折与悬念，节拍数量应匹配字数预算）\n"
        "内容要具体、可执行。"
    )

    result = generate_with_openrouter(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        preferred_keywords=["qwen", "mistral", "gemini", "llama"],
        role="controller",
    )
    model_id = result["model"]["id"]
    content = result["completion"]["choices"][0]["message"]["content"]

    if "Beat Sheet" in content:
        design_brief, beat_sheet = content.split("Beat Sheet", 1)
        design_brief = design_brief.strip()
        beat_sheet = "Beat Sheet" + beat_sheet.strip()
    else:
        design_brief = content.strip()
        beat_sheet = "Beat Sheet\n- Establish opening tension\n- Escalate conflict\n- Land a turn or reveal"

    existing = db.scalar(select(ChapterPlan).where(ChapterPlan.chapter_id == chapter_id))
    if existing is None:
        plan = ChapterPlan(
            project_id=project_id,
            book_id=chapter.book_id,
            chapter_id=chapter_id,
            plot_line_id=plot_line_id,
            title=chapter.title,
            design_brief=design_brief,
            beat_sheet=beat_sheet,
            asset_summary=asset_summary,
            selected_model=model_id,
            status="designed",
        )
        db.add(plan)
    else:
        existing.plot_line_id = plot_line_id
        existing.book_id = chapter.book_id
        existing.title = chapter.title
        existing.design_brief = design_brief
        existing.beat_sheet = beat_sheet
        existing.asset_summary = asset_summary
        existing.selected_model = model_id
        existing.status = "designed"
        plan = existing

    db.commit()
    db.refresh(plan)
    sync_chapter_plan_to_neo4j(plan)
    return plan


def generate_chapter_draft(
    db: Session,
    project_id: int,
    chapter_id: int,
    style_hint: str | None = None,
    word_target: int | None = None,
) -> Chapter:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.project_id != project_id:
        raise ValueError("Chapter not found in project")

    plan = db.scalar(select(ChapterPlan).where(ChapterPlan.chapter_id == chapter_id))
    if plan is None:
        raise ValueError("Chapter plan not found; design the chapter first")

    constraints = load_project_constraints(db, project_id)
    effective_target = word_target or constraints.word_target
    effective_style = style_hint or constraints.style_hint()
    constraint_block = build_constraint_block(constraints, word_target=effective_target)
    preferred = ["qwen", "mistral", "gemini", "llama"]

    system_prompt = (
        "你是一位技艺娴熟的小说代笔作者。请基于章节计划撰写本章正文，"
        "与已给资产保持连续性，场景推进有力，并严格遵守创作约束（题材、风格、"
        "基调、字数）。只输出正文本身，不要输出解释或标题以外的元信息。"
    )
    base_user_prompt = (
        f"{constraint_block}\n\n"
        f"章节标题：{chapter.title}\n"
        f"风格提示：{effective_style}\n\n"
        f"设计概要(Design brief)：\n{plan.design_brief}\n\n"
        f"节拍表(Beat sheet)：\n{plan.beat_sheet}\n\n"
        f"项目资产：\n{plan.asset_summary}\n\n"
        "请写出完整、连贯、文笔打磨过的本章正文。"
    )

    result = generate_with_openrouter(
        system_prompt=system_prompt,
        user_prompt=base_user_prompt,
        preferred_keywords=preferred,
        role="creator",
    )
    model_id = result["model"]["id"]
    content = extract_message_content(result.get("completion"))
    content = _enforce_word_target(
        content,
        constraints=constraints,
        word_target=effective_target,
        system_prompt=system_prompt,
        base_user_prompt=base_user_prompt,
        preferred_keywords=preferred,
    )
    chapter.draft_content = content
    chapter.word_count = count_words(content)
    chapter.status = "drafted"
    chapter.version = (chapter.version or 1) + 1
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    _persist_chapter_version(
        db,
        chapter=chapter,
        content=content,
        model_id=model_id,
        operation_type="draft_generation",
        instruction=style_hint,
        summary=chapter.summary,
    )
    sync_chapter_to_neo4j(chapter)
    return chapter


def revise_chapter_draft(
    db: Session,
    project_id: int,
    chapter_id: int,
    revision_focus: str | None = None,
    style_hint: str | None = None,
    word_target: int | None = None,
) -> dict:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.project_id != project_id:
        raise ValueError("Chapter not found in project")
    if not chapter.draft_content:
        raise ValueError("Chapter draft not found; generate the chapter first")

    plan = db.scalar(select(ChapterPlan).where(ChapterPlan.chapter_id == chapter_id))
    if plan is None:
        raise ValueError("Chapter plan not found; design the chapter first")

    assets = _collect_chapter_assets(db, project_id, plan.plot_line_id)
    asset_summary = _build_asset_summary(assets)
    constraints = load_project_constraints(db, project_id)
    effective_target = word_target or constraints.word_target
    effective_style = style_hint or constraints.style_hint()
    constraint_block = build_constraint_block(constraints, word_target=effective_target)
    preferred = ["qwen", "mistral", "gemini", "llama"]

    consistency_system_prompt = (
        "你是一位严格的小说一致性审校编辑。请对照章节计划、项目资产与创作约束审查草稿，"
        "输出三个小节：Consistency Summary、Issues、Suggested Fixes。"
    )
    consistency_user_prompt = (
        f"{constraint_block}\n\n"
        f"章节标题：{chapter.title}\n"
        f"修订重点：{revision_focus or ''}\n\n"
        f"设计概要：\n{plan.design_brief}\n\n"
        f"节拍表：\n{plan.beat_sheet}\n\n"
        f"项目资产：\n{asset_summary}\n\n"
        f"草稿：\n{chapter.draft_content}"
    )
    consistency_result = generate_with_openrouter(
        system_prompt=consistency_system_prompt,
        user_prompt=consistency_user_prompt,
        preferred_keywords=preferred,
        role="controller",
    )
    consistency_model_id = consistency_result["model"]["id"]
    consistency_report = extract_message_content(consistency_result.get("completion"))

    rewrite_system_prompt = (
        "你是一位资深小说修订师。请依据一致性报告重写本章正文，保持故事推进力、"
        "人物口吻与可读性，并严格遵守创作约束（题材、风格、基调、字数）。"
        "只输出重写后的正文。"
    )
    rewrite_user_prompt = (
        f"{constraint_block}\n\n"
        f"章节标题：{chapter.title}\n"
        f"风格提示：{effective_style}\n"
        f"修订重点：{revision_focus or '在保留最佳场景的前提下修复一致性问题。'}\n\n"
        f"设计概要：\n{plan.design_brief}\n\n"
        f"节拍表：\n{plan.beat_sheet}\n\n"
        f"项目资产：\n{asset_summary}\n\n"
        f"一致性报告：\n{consistency_report}\n\n"
        f"当前草稿：\n{chapter.draft_content}\n\n"
        "请重写出完整的本章正文。"
    )
    rewrite_result = generate_with_openrouter(
        system_prompt=rewrite_system_prompt,
        user_prompt=rewrite_user_prompt,
        preferred_keywords=preferred,
        role="creator",
    )
    rewrite_model_id = rewrite_result["model"]["id"]
    revised_content = extract_message_content(rewrite_result.get("completion"))
    revised_content = _enforce_word_target(
        revised_content,
        constraints=constraints,
        word_target=effective_target,
        system_prompt=rewrite_system_prompt,
        base_user_prompt=rewrite_user_prompt,
        preferred_keywords=preferred,
    )

    chapter.draft_content = revised_content
    chapter.final_content = revised_content
    chapter.word_count = count_words(revised_content)
    chapter.status = "completed"
    chapter.version = (chapter.version or 1) + 1
    db.add(chapter)
    db.commit()
    db.refresh(chapter)

    version = _persist_chapter_version(
        db,
        chapter=chapter,
        content=revised_content,
        model_id=rewrite_model_id,
        operation_type="revision",
        instruction=revision_focus or style_hint,
        consistency_report=consistency_report,
        summary=chapter.summary,
    )
    sync_chapter_to_neo4j(chapter)

    # AI 写完一节：自动触发一次故事图谱规范化（异步、不阻塞章节保存）。
    # 任务调度内部已加节流，避免每节都拉 AI。
    _maybe_auto_trigger_story_graph(
        project_id=project_id,
        chapter_id=chapter.id,
        chapter_title=chapter.title,
    )

    return {
        "chapter": chapter,
        "version": version,
        "consistency_report": consistency_report,
        "consistency_model": consistency_model_id,
        "rewrite_model": rewrite_model_id,
    }


# ---------------------------------------------------------------------------
# 故事图谱自动触发
# ---------------------------------------------------------------------------


def _recent_story_graph_task(db: Session, project_id: int) -> AITask | None:
    """返回项目最近一次 ``story_graph_generation`` 任务（仍在排队 / 运行 / 刚完成）。"""
    return db.scalar(
        select(AITask)
        .where(
            AITask.project_id == project_id,
            AITask.task_type == "story_graph_generation",
        )
        .order_by(AITask.created_at.desc())
        .limit(1)
    )


def _maybe_auto_trigger_story_graph(
    *,
    project_id: int,
    chapter_id: int,
    chapter_title: str,
) -> None:
    """AI 完成一节后异步触发一次故事图谱规范化。

    设计要点：
    * 不在请求线程里同步跑 AI（耗时且会拖慢章节保存响应）。
    * 通过新建 ``story_graph_generation`` 任务 + 守护线程消费，保留任务列表可观测性。
    * 加节流：相邻 ``_STORY_GRAPH_AUTO_COOLDOWN`` 秒内若已存在任务则跳过，
      防止短时间内写多节时反复拉 AI。
    """
    cooldown_db = SessionLocal()
    try:
        last_task = _recent_story_graph_task(cooldown_db, project_id)
        if last_task is not None and last_task.created_at is not None:
            # 任务的 created_at 通常带时区；做一次 safe compare
            now = datetime.now(timezone.utc)
            created_at = last_task.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if now - created_at < _STORY_GRAPH_AUTO_COOLDOWN:
                logger.info(
                    "Skip auto story graph regeneration: project=%s cooldown active (last task %s at %s)",
                    project_id, last_task.id, created_at,
                )
                return
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cooldown check failed (proceeding with trigger): %s", exc)
    finally:
        cooldown_db.close()

    trigger_db = SessionLocal()
    task: AITask | None = None
    try:
        task = create_task(
            trigger_db,
            project_id,
            AITaskCreate(
                chapter_id=chapter_id,
                task_type="story_graph_generation",
                module_type="story_graph",
                title=f"自动生成故事图谱：{chapter_title or f'第{chapter_id}章'}",
                input_payload="auto_trigger:chapter_completed",
                plan_text=(
                    "扫描项目内角色 / 剧情 / 事件 / 世界观资产，"
                    "由 AI 规范化生成 StoryArc / StoryTheme / StoryEvent 节点，"
                    "并同步写入 Neo4j。"
                ),
                status="pending",
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to enqueue auto story graph task: %s", exc)
        trigger_db.close()
        return

    task_id = task.id
    project_id_snapshot = project_id
    trigger_db.close()

    def _runner() -> None:
        bg_db = SessionLocal()
        try:
            from app.services.story_graph_generation_service import generate_normalized_story_graph

            current = bg_db.get(AITask, task_id)
            if current is not None:
                current.status = "running"
                current.started_at = datetime.now(timezone.utc)
                bg_db.add(current)
                bg_db.commit()

            try:
                summary = generate_normalized_story_graph(
                    bg_db, project_id_snapshot, task_id=task_id,
                )
                finished = bg_db.get(AITask, task_id)
                if finished is not None:
                    finished.status = "completed"
                    finished.finished_at = datetime.now(timezone.utc)
                    finished.output_payload = json.dumps(_safe_summary(summary), ensure_ascii=False)[:2000]
                    bg_db.add(finished)
                    bg_db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.error("Auto story graph generation failed: %s", exc, exc_info=True)
                failed = bg_db.get(AITask, task_id)
                if failed is not None:
                    failed.status = "failed"
                    failed.finished_at = datetime.now(timezone.utc)
                    failed.error_message = str(exc)[:500]
                    bg_db.add(failed)
                    bg_db.commit()
        finally:
            bg_db.close()

    thread = threading.Thread(target=_runner, name=f"story-graph-auto-{task_id}", daemon=True)
    thread.start()


def _safe_summary(summary: dict | None) -> dict:
    """把 generate_normalized_story_graph 的回包压缩成可序列化 dict。"""
    if not isinstance(summary, dict):
        return {"status": "unknown"}
    out: dict = {}
    for k, v in summary.items():
        try:
            json.dumps(v, ensure_ascii=False)
            out[k] = v
        except TypeError:
            out[k] = str(v)
    return out
