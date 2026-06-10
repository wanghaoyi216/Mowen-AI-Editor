"""Chapter Loop Executor Service — LangGraph DAG + SubAgent parallel execution.

This service provides an ENHANCED chapter execution path that uses a LangGraph
StateGraph with parallel SubAgents, instead of the linear 9-step workflow.

Key features:
- Parallel SubAgents: character design, plot design, worldbook consistency check
- ReAct loop for chapter content generation
- Consistency review + conditional revision
- Rate limiter integration before every LLM call
- Graceful fallback to linear workflow if DAG execution fails
- INDEPENDENT of workflow_orchestration_service — orchestrator can choose either path
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, TypedDict

from sqlalchemy.orm import Session

from app.schemas.chapter import ChapterCreate
from app.schemas.chapter_version import ChapterRevisionRequest
from app.services.agent_event_bus import AgentEvent, bus, publish_text_delta
from app.services.chapter_ai_service import build_chapter_plan, generate_chapter_draft, revise_chapter_draft
from app.services.chapter_consistency_service import run_chapter_consistency_check
from app.services.chapter_service import create_chapter, get_chapter
from app.services.rate_limiter import rate_limiter
from app.services.workflow_orchestration_service import execute_auto_novel_workflow
from app.schemas.workflow_orchestration import AutoNovelWorkflowRequest


# --- 事件发送辅助（与 orchestrator 中同名函数保持一致）---
_TASK_ID_KEY = "_task_id"  # DAG state 中携带 task_id 的键


def _emit(state: ChapterDAGState | dict | None, event_type: str, **data: Any) -> None:
    """在 DAG 节点内部发送事件。``state`` 可以是 dict 或 ChapterDAGState。"""
    if not state:
        return
    task_id = state.get(_TASK_ID_KEY) if isinstance(state, dict) else getattr(state, _TASK_ID_KEY, None)
    if not task_id:
        return
    try:
        bus.publish(
            AgentEvent(
                event_type=event_type,
                task_id=task_id,
                phase="chapter_loop",
                data=data,
            )
        )
    except Exception as emit_exc:  # noqa: BLE001
        logger.debug("[chapter_loop] _emit failed: %s", emit_exc)

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover — optional compatibility until langgraph is installed everywhere
    END = "__end__"
    StateGraph = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DAG State
# ---------------------------------------------------------------------------


class ChapterDAGState(TypedDict):
    """State carried through the chapter DAG execution graph."""

    db: Session
    project_id: int
    chapter_plan: dict[str, Any]
    novel_outline: dict[str, Any]
    previous_chapters_context: str

    # SubAgent outputs (parallel phase)
    character_design: dict[str, Any]
    plot_design: dict[str, Any]
    worldbook_check: dict[str, Any]

    # Writer / Reviewer outputs
    chapter_draft: dict[str, Any]
    consistency_report: str
    needs_revision: bool
    revision_result: dict[str, Any]

    # Execution metadata
    chapter: Any  # Chapter ORM model
    errors: list[str]
    elapsed_seconds: float
    mode: str  # "dag" or "fallback_linear"
    subagent_results: dict[str, Any]

    # Event bus 任务 ID（由 orchestrator 注入）
    _task_id: int
    # 当前创作所属 book（由 orchestrator 注入；prompt 注入用）
    _current_book_id: int | None
    _current_book_name: str | None


# ---------------------------------------------------------------------------
# DAG Node Functions
# ---------------------------------------------------------------------------


def _acquire_rate_limit() -> None:
    """Acquire a rate-limiter token before making an LLM call."""
    rate_limiter.acquire()


def _safe_log(message: str, **kwargs: Any) -> None:
    logger.info(message, **kwargs)


def _summarize(value: object, limit: int = 200) -> str:
    text = str(value)
    return " ".join(text.split())[:limit]


# --- Planner Node ----------------------------------------------------------

def planner_node(state: ChapterDAGState) -> dict[str, Any]:
    """Analyze the chapter plan and prepare sub-task payloads for parallel agents."""
    _safe_log("[DAG Planner] Analyzing chapter plan")
    _acquire_rate_limit()
    _emit(state, "tool_call", agent="planner", tool="analyze", chapter_no=state["chapter_plan"].get("chapter_no"))

    chapter_plan = state["chapter_plan"]
    novel_outline = state["novel_outline"]

    # Build character task payload
    character_task = {
        "chapter_title": chapter_plan.get("title", ""),
        "characters_involved": chapter_plan.get("characters_involved", []),
        "main_characters": novel_outline.get("main_characters", []),
        "theme": chapter_plan.get("theme", ""),
    }

    # Build plot task payload
    plot_task = {
        "chapter_title": chapter_plan.get("title", ""),
        "key_events": chapter_plan.get("key_events", []),
        "theme": chapter_plan.get("theme", ""),
        "genre": novel_outline.get("genre", ""),
    }

    # Build worldbook check payload
    worldbook_task = {
        "chapter_plan": chapter_plan,
        "novel_outline": novel_outline,
    }

    return {
        "character_design": {"task": character_task, "status": "ready"},
        "plot_design": {"task": plot_task, "status": "ready"},
        "worldbook_check": {"task": worldbook_task, "status": "ready"},
    }


# --- SubAgent: Character Design --------------------------------------------

def character_agent_node(state: ChapterDAGState) -> dict[str, Any]:
    """SubAgent 1: Design/update characters for this chapter (runs in parallel)."""
    _safe_log("[Character SubAgent] Designing characters")
    _acquire_rate_limit()

    task = state["character_design"].get("task", {})
    chapter_title = task.get("chapter_title", "")
    characters_involved = task.get("characters_involved", [])
    main_characters = task.get("main_characters", [])
    theme = task.get("theme", "")

    system_prompt = (
        "你是一位资深的人物设计师，负责为当前章节设计或更新角色设定。\n"
        "请根据章节主题、涉及角色列表和主要角色档案，输出角色设计要点。\n"
        "输出纯 JSON 格式。"
    )
    user_prompt = (
        f"章节标题：{chapter_title}\n"
        f"本章主题：{theme}\n"
        f"涉及角色：{', '.join(characters_involved) if characters_involved else '无'}\n\n"
        f"主要角色档案：\n"
        + json.dumps(main_characters, ensure_ascii=False)[:2000]
        + "\n\n"
        "请为涉及的角色输出设计要点，包括：\n"
        "1. 本章角色动机\n"
        "2. 情绪状态\n"
        "3. 关键行为特征\n"
        "4. 与其他角色的互动要点\n"
    )

    try:
        from app.services.openrouter_service import generate_with_openrouter

        result = generate_with_openrouter(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            stream=True,
            on_delta=lambda c: publish_text_delta(
                state.get(_TASK_ID_KEY), "character_agent", "character_agent", c
            ),
            role="controller",
        )
        content = result["completion"]["choices"][0]["message"]["content"]
        design = _parse_json_safely(content)
    except Exception as exc:
        logger.warning("[Character SubAgent] Failed, using fallback: %s", exc)
        design = {
            "characters_involved": characters_involved,
            "fallback": True,
            "error": str(exc)[:200],
        }

    return {
        "character_design": {
            "design": design,
            "status": "completed",
            "agent": "character_subagent",
        }
    }


# --- SubAgent: Plot Design -------------------------------------------------

def plot_agent_node(state: ChapterDAGState) -> dict[str, Any]:
    """SubAgent 2: Design plot beats for this chapter (runs in parallel)."""
    _safe_log("[Plot SubAgent] Designing plot beats")
    _acquire_rate_limit()
    _emit(state, "tool_call", agent="plot_agent", tool="llm_generate",
          chapter_no=state["chapter_plan"].get("chapter_no"))

    task = state["plot_design"].get("task", {})
    chapter_title = task.get("chapter_title", "")
    key_events = task.get("key_events", [])
    theme = task.get("theme", "")
    genre = task.get("genre", "")

    system_prompt = (
        "你是一位资深的剧情策划，负责为当前章节设计剧情节拍和事件编排。\n"
        "请根据章节主题、关键事件和题材类型，输出剧情设计要点。\n"
        "输出纯 JSON 格式。"
    )
    user_prompt = (
        f"章节标题：{chapter_title}\n"
        f"本章主题：{theme}\n"
        f"关键事件：{'、'.join(key_events) if key_events else '无'}\n"
        f"题材类型：{genre}\n\n"
        "请输出剧情设计要点，包括：\n"
        "1. 开场节拍（hook）\n"
        "2. 发展节拍（2-3个）\n"
        "3. 高潮节拍\n"
        "4. 收尾节拍（含悬念/转折）\n"
        "5. 每个节拍的冲突点\n"
    )

    try:
        from app.services.openrouter_service import generate_with_openrouter

        result = generate_with_openrouter(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            stream=True,
            on_delta=lambda c: publish_text_delta(
                state.get(_TASK_ID_KEY), "plot_agent", "plot_agent", c
            ),
            role="controller",
        )
        content = result["completion"]["choices"][0]["message"]["content"]
        design = _parse_json_safely(content)
    except Exception as exc:
        logger.warning("[Plot SubAgent] Failed, using fallback: %s", exc)
        design = {
            "key_events": key_events,
            "fallback": True,
            "error": str(exc)[:200],
        }

    return {
        "plot_design": {
            "design": design,
            "status": "completed",
            "agent": "plot_subagent",
        }
    }


# --- SubAgent: Worldbook Consistency Check ---------------------------------

def worldbook_agent_node(state: ChapterDAGState) -> dict[str, Any]:
    """SubAgent 3: Check worldbook consistency for this chapter (runs in parallel)."""
    _safe_log("[Worldbook SubAgent] Checking worldbook consistency")
    _acquire_rate_limit()

    task = state["worldbook_check"].get("task", {})
    chapter_plan = task.get("chapter_plan", {})
    novel_outline = task.get("novel_outline", {})

    system_prompt = (
        "你是一位严谨的世界观审核员，负责检查章节计划与小说世界观的一致性。\n"
        "请分析章节计划是否与已有世界观设定冲突。\n"
        "输出纯 JSON 格式。"
    )
    user_prompt = (
        f"章节计划：\n"
        f"标题：{chapter_plan.get('title', '')}\n"
        f"主题：{chapter_plan.get('theme', '')}\n"
        f"关键事件：{json.dumps(chapter_plan.get('key_events', []), ensure_ascii=False)}\n\n"
        f"小说大纲概况：\n"
        f"标题：{novel_outline.get('title', '')}\n"
        f"题材：{novel_outline.get('genre', '')}\n\n"
        "请检查以下方面：\n"
        "1. 世界观一致性（物理法则、魔法体系、社会结构等）\n"
        "2. 时间线合理性\n"
        "3. 角色行为是否符合设定\n"
        "4. 潜在冲突和风险点\n"
    )

    try:
        from app.services.openrouter_service import generate_with_openrouter

        result = generate_with_openrouter(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            stream=True,
            on_delta=lambda c: publish_text_delta(
                state.get(_TASK_ID_KEY), "worldbook_agent", "worldbook_agent", c
            ),
            role="controller",
        )
        content = result["completion"]["choices"][0]["message"]["content"]
        check = _parse_json_safely(content)
    except Exception as exc:
        logger.warning("[Worldbook SubAgent] Failed, using fallback: %s", exc)
        check = {
            "fallback": True,
            "error": str(exc)[:200],
            "is_consistent": True,  # 默认通过，让后续一致性检查兜底
        }

    return {
        "worldbook_check": {
            "check": check,
            "status": "completed",
            "agent": "worldbook_subagent",
        }
    }


# --- Writer Node -----------------------------------------------------------

def writer_node(state: ChapterDAGState) -> dict[str, Any]:
    """Generate chapter content using SubAgent outputs as context."""
    _safe_log("[Writer] Generating chapter content")
    _acquire_rate_limit()

    db = state["db"]
    project_id = state["project_id"]
    chapter_plan = state["chapter_plan"]
    previous_context = state["previous_chapters_context"]

    character_design = state.get("character_design", {})
    plot_design = state.get("plot_design", {})
    worldbook_check = state.get("worldbook_check", {})

    # Build comprehensive writing prompt from SubAgent results
    character_info = json.dumps(character_design.get("design", {}), ensure_ascii=False)
    plot_info = json.dumps(plot_design.get("design", {}), ensure_ascii=False)
    worldbook_info = json.dumps(worldbook_check.get("check", {}), ensure_ascii=False)

    # 加载项目级创作约束（题材/风格/基调/受众/字数），真正注入到写作 prompt
    from app.services.writing_constraints_service import (
        build_constraint_block,
        count_words,
        load_project_constraints,
    )

    constraints = load_project_constraints(db, project_id)
    plan_target = chapter_plan.get("word_target") or constraints.word_target
    try:
        word_target = int(plan_target)
    except (TypeError, ValueError):
        word_target = constraints.word_target
    word_target = max(
        constraints.min_words_per_chapter,
        min(word_target, constraints.max_words_per_chapter),
    )
    constraint_block = build_constraint_block(constraints, word_target=word_target)

    system_prompt = (
        "你是一位技艺娴熟的小说代笔作者，写作时必须：\n"
        "1. 严格遵循章节计划\n"
        "2. 与角色设计保持人物一致性\n"
        "3. 纳入剧情设计中的所有节拍\n"
        "4. 遵守世界观约束\n"
        "5. 与前文自然衔接\n"
        "6. 严格遵守下方创作约束（题材、风格、基调、字数）\n"
        "用打磨过、画面感强的文笔写作，场景推进有力。只输出正文。"
    )

    # Resolve current book (fallback to project default if state has none)
    book_name = state.get("_current_book_name") or "默认书"
    book_id_for_writer = state.get("_current_book_id")

    base_user_prompt = (
        f"{constraint_block}\n\n"
        f"当前书名：{book_name}（book_id={book_id_for_writer}）\n"
        f"章节标题：{chapter_plan.get('title', '')}\n"
        f"本章主题：{chapter_plan.get('theme', '')}\n\n"
        f"角色设计：\n{character_info[:2000]}\n\n"
        f"剧情设计：\n{plot_info[:2000]}\n\n"
        f"世界观约束：\n{worldbook_info[:1000]}\n\n"
        f"前文摘要：\n{previous_context[:3000]}\n\n"
        f"关键事件：{', '.join(chapter_plan.get('key_events', []))}\n\n"
        "约束：禁止引用其他书的角色；只能使用当前书中已定义的 character 设定。\n"
        "请写出完整、连贯、文笔打磨过的本章正文。"
    )

    try:
        from app.services.openrouter_service import (
            extract_message_content,
            generate_with_openrouter,
        )

        result = generate_with_openrouter(
            system_prompt=system_prompt,
            user_prompt=base_user_prompt,
            preferred_keywords=["qwen", "mistral", "gemini"],
            stream=True,
            on_delta=lambda c: publish_text_delta(
                state.get(_TASK_ID_KEY), "writer", "writer", c
            ),
            role="creator",
        )
        content = extract_message_content(result.get("completion"))
        model_id = result["model"]["id"]
        content = _enforce_writer_word_target(
            content,
            constraints=constraints,
            word_target=word_target,
            system_prompt=system_prompt,
            base_user_prompt=base_user_prompt,
            on_delta=lambda c: publish_text_delta(
                state.get(_TASK_ID_KEY), "writer", "writer", c
            ),
        )
    except Exception as exc:
        logger.error("[Writer] LLM generation failed: %s", exc)
        raise

    # Persist the chapter to the database
    chapter = _persist_chapter_from_content(
        db=db,
        project_id=project_id,
        chapter_plan=chapter_plan,
        content=content,
        model_id=model_id,
        book_id=book_id_for_writer,
    )

    return {
        "chapter_draft": {
            "content": content,
            "model_id": model_id,
            "word_count": count_words(content),
        },
        "chapter": chapter,
    }


# --- Reviewer Node ---------------------------------------------------------

def reviewer_node(state: ChapterDAGState) -> dict[str, Any]:
    """Check chapter consistency and suggest revisions."""
    _safe_log("[Reviewer] Checking chapter consistency")
    _acquire_rate_limit()

    db = state["db"]
    project_id = state["project_id"]
    chapter = state.get("chapter")

    if chapter is None:
        return {
            "consistency_report": "No chapter to review",
            "needs_revision": False,
        }

    try:
        # Use the existing consistency check service
        consistency_result = run_chapter_consistency_check(db, project_id, chapter.id)
        report = consistency_result.get("report", "")
        issues = consistency_result.get("issues", [])

        # Determine if revision is needed
        needs_revision = bool(issues) or "conflict" in report.lower() or "inconsistent" in report.lower()
    except Exception as exc:
        logger.warning("[Reviewer] Consistency check failed: %s", exc)
        report = f"Consistency check error: {str(exc)[:200]}"
        needs_revision = False  # Don't trigger revision on review failure

    return {
        "consistency_report": report,
        "needs_revision": needs_revision,
    }


# --- Reviser Node ----------------------------------------------------------

def reviser_node(state: ChapterDAGState) -> dict[str, Any]:
    """Apply revisions based on the consistency report."""
    _safe_log("[Reviser] Applying revisions to chapter")
    _acquire_rate_limit()
    _emit(state, "tool_call", agent="reviser", tool="llm_generate",
          chapter_no=state["chapter_plan"].get("chapter_no"))

    db = state["db"]
    project_id = state["project_id"]
    chapter = state.get("chapter")
    report = state.get("consistency_report", "")

    if chapter is None:
        return {
            "revision_result": {"error": "No chapter to revise"},
        }

    # Build revision focus from the consistency report
    revision_focus = (
        f"请根据以下一致性报告修订章节：\n{report[:1000]}\n\n"
        "重点关注：角色设定一致性、剧情逻辑连贯性、世界观一致性。"
    )

    try:
        result = revise_chapter_draft(
            db,
            project_id=project_id,
            chapter_id=chapter.id,
            revision_focus=revision_focus,
            style_hint=None,
            word_target=state["chapter_plan"].get("word_target", 4000),
        )
    except Exception as exc:
        logger.warning("[Reviser] Revision failed: %s", exc)
        result = {
            "chapter": chapter,
            "version": None,
            "error": str(exc)[:200],
        }

    return {
        "revision_result": {
            "chapter": result.get("chapter"),
            "version": result.get("version"),
            "status": "completed",
        },
        "chapter": result.get("chapter", chapter),
    }


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------


def _route_reviewer(state: ChapterDAGState) -> str:
    """Conditional routing: reviewer -> reviser or reviewer -> END."""
    if state.get("needs_revision", False):
        return "reviser"
    return END


def build_chapter_dag_graph() -> Any:
    """Build a LangGraph StateGraph for chapter execution.

    Nodes:
    - planner: analyzes chapter plan and creates sub-tasks
    - character_agent: designs/updates characters for this chapter
    - plot_agent: designs plot beats for this chapter
    - worldbook_agent: checks worldbook consistency
    - writer: generates chapter content
    - reviewer: checks consistency and suggests revisions
    - reviser: applies revisions

    Edges:
    - planner -> [character_agent, plot_agent, worldbook_agent] (parallel)
    - [character_agent, plot_agent, worldbook_agent] -> writer
    - writer -> reviewer -> reviser (conditional)
    - reviser -> END
    """
    if StateGraph is None:
        logger.warning("LangGraph not available, cannot build DAG graph")
        return None

    graph = StateGraph(ChapterDAGState)

    # Add nodes
    graph.add_node("planner", planner_node)
    graph.add_node("character_agent", character_agent_node)
    graph.add_node("plot_agent", plot_agent_node)
    graph.add_node("worldbook_agent", worldbook_agent_node)
    graph.add_node("writer", writer_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("reviser", reviser_node)

    # Entry point
    graph.set_entry_point("planner")

    # Planner -> parallel SubAgents
    graph.add_edge("planner", "character_agent")
    graph.add_edge("planner", "plot_agent")
    graph.add_edge("planner", "worldbook_agent")

    # Parallel SubAgents -> writer (LangGraph waits for all before proceeding)
    graph.add_edge("character_agent", "writer")
    graph.add_edge("plot_agent", "writer")
    graph.add_edge("worldbook_agent", "writer")

    # Writer -> reviewer
    graph.add_edge("writer", "reviewer")

    # Reviewer -> reviser or END (conditional)
    graph.add_conditional_edges(
        "reviewer",
        _route_reviewer,
        {"reviser": "reviser", END: END},
    )

    # Reviser -> END
    graph.add_edge("reviser", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def execute_chapter_with_subagents(
    db: Session,
    project_id: int,
    chapter_plan: dict,
    novel_outline: dict,
    previous_chapters_context: str = "",
    task_id: int | None = None,
    book_id: int | None = None,
    book_name: str | None = None,
) -> dict:
    """Execute a single chapter using SubAgent parallel + ReAct loop.

    Instead of calling the linear workflow, this uses:
    1. SubAgent 1: Character design for this chapter (parallel)
    2. SubAgent 2: Plot design for this chapter (parallel)
    3. SubAgent 3: Worldbook consistency check (parallel)
    4. ReAct Loop: Generate chapter content
    5. Consistency check + revision

    Falls back to the linear workflow if DAG execution fails.
    """
    start_time = time.perf_counter()
    ch_no = chapter_plan.get("chapter_no", "?")
    ch_title = chapter_plan.get("title", f"第{ch_no}章")

    logger.info(
        "[Chapter DAG Executor] Starting: chapter_no=%s, title=%s, book_id=%s, book_name=%s",
        ch_no,
        ch_title,
        book_id,
        book_name,
    )

    try:
        # Build and run the DAG graph
        compiled_graph = build_chapter_dag_graph()

        if compiled_graph is None:
            logger.warning(
                "[Chapter DAG Executor] LangGraph unavailable, falling back to linear workflow"
            )
            return _fallback_to_linear_workflow(
                db=db,
                project_id=project_id,
                chapter_plan=chapter_plan,
                novel_outline=novel_outline,
                previous_chapters_context=previous_chapters_context,
            )

        initial_state: ChapterDAGState = {
            "db": db,
            "project_id": project_id,
            "chapter_plan": chapter_plan,
            "novel_outline": novel_outline,
            "previous_chapters_context": previous_chapters_context,
            "character_design": {},
            "plot_design": {},
            "worldbook_check": {},
            "chapter_draft": {},
            "consistency_report": "",
            "needs_revision": False,
            "revision_result": {},
            "chapter": None,
            "errors": [],
            "elapsed_seconds": 0.0,
            "mode": "dag",
            "subagent_results": {},
            "_task_id": task_id or 0,
            "_current_book_id": book_id,
            "_current_book_name": book_name or "默认书",
        }

        # Execute the graph
        final_state = compiled_graph.invoke(initial_state)

        elapsed = time.perf_counter() - start_time
        chapter = final_state.get("chapter")

        result = {
            "chapter": chapter,
            "chapter_no": ch_no,
            "title": ch_title,
            "status": "completed",
            "mode": "dag",
            "elapsed_seconds": round(elapsed, 2),
            "consistency_report": final_state.get("consistency_report", ""),
            "needs_revision": final_state.get("needs_revision", False),
            "subagent_results": {
                "character_agent": final_state.get("character_design", {}),
                "plot_agent": final_state.get("plot_design", {}),
                "worldbook_agent": final_state.get("worldbook_check", {}),
            },
            "errors": final_state.get("errors", []),
        }

        word_count = getattr(chapter, "word_count", 0) if chapter else 0
        logger.info(
            "[Chapter DAG Executor] Completed: chapter_no=%s, title=%s, words=%d, mode=dag, elapsed=%.1fs",
            ch_no,
            ch_title,
            word_count,
            elapsed,
        )

        return result

    except Exception as exc:
        logger.error(
            "[Chapter DAG Executor] DAG execution failed: %s, falling back to linear workflow",
            exc,
            exc_info=True,
        )
        return _fallback_to_linear_workflow(
            db=db,
            project_id=project_id,
            chapter_plan=chapter_plan,
            novel_outline=novel_outline,
            previous_chapters_context=previous_chapters_context,
            error=str(exc)[:300],
        )


def _fallback_to_linear_workflow(
    db: Session,
    project_id: int,
    chapter_plan: dict,
    novel_outline: dict,
    previous_chapters_context: str = "",
    error: str = "",
) -> dict:
    """Fallback to the linear 9-step workflow when DAG execution fails."""
    start_time = time.perf_counter()
    ch_no = chapter_plan.get("chapter_no", "?")
    ch_title = chapter_plan.get("title", f"第{ch_no}章")

    logger.info(
        "[Chapter DAG Executor] Fallback: linear workflow for chapter_no=%s, title=%s",
        ch_no,
        ch_title,
    )

    # Build design guidance from chapter plan
    design_guidance_parts = [f"本章主题：{chapter_plan.get('theme', '')}"]
    key_events = chapter_plan.get("key_events", [])
    if key_events:
        design_guidance_parts.append(f"关键事件：{'、'.join(key_events)}")
    characters_involved = chapter_plan.get("characters_involved", [])
    if characters_involved:
        design_guidance_parts.append(f"涉及角色：{', '.join(characters_involved)}")
    design_guidance = " | ".join(design_guidance_parts)

    payload = AutoNovelWorkflowRequest(
        title=novel_outline.get("title", ""),
        query_text=f"{novel_outline.get('genre', '')} - {novel_outline.get('title', '')}",
        chapter_no=int(ch_no) if isinstance(ch_no, int) else 1,
        chapter_title=ch_title,
        chapter_summary=chapter_plan.get("theme", ""),
        chapter_objective=chapter_plan.get("theme", ""),
        design_guidance=design_guidance,
        style_hint=None,
        revision_focus=None,
        word_target=chapter_plan.get("word_target", 4000),
    )

    step_result = execute_auto_novel_workflow(
        db=db,
        project_id=project_id,
        payload=payload,
        task_id=None,
    )

    elapsed = time.perf_counter() - start_time
    chapter = step_result.get("chapter")
    word_count = getattr(chapter, "word_count", 0) if chapter else 0

    return {
        "chapter": chapter,
        "chapter_no": ch_no,
        "title": ch_title,
        "status": "completed",
        "mode": "fallback_linear",
        "elapsed_seconds": round(elapsed, 2),
        "consistency_report": str(step_result.get("consistency_report", ""))[:500],
        "needs_revision": False,
        "subagent_results": {},
        "errors": [error] if error else [],
        "fallback_reason": error or "DAG execution failed",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_WRITER_WORD_ENFORCE_MIN_RATIO = 0.8
_WRITER_WORD_ENFORCE_MAX_ROUNDS = 2


def _enforce_writer_word_target(
    content: str,
    *,
    constraints: Any,
    word_target: int,
    system_prompt: str,
    base_user_prompt: str,
    on_delta: Callable[[str], None] | None = None,
) -> str:
    """Writer 节点字数强制：正文不足时驱动模型续写补足（最多 2 轮）。"""
    from app.services.openrouter_service import extract_message_content, generate_with_openrouter
    from app.services.writing_constraints_service import build_word_budget_line, count_words

    min_acceptable = max(
        constraints.min_words_per_chapter,
        int(word_target * _WRITER_WORD_ENFORCE_MIN_RATIO),
    )
    current = count_words(content)
    rounds = 0
    while current < min_acceptable and rounds < _WRITER_WORD_ENFORCE_MAX_ROUNDS:
        rounds += 1
        budget_line = build_word_budget_line(
            constraints, word_target=word_target, current_words=current
        )
        continuation_prompt = (
            f"{base_user_prompt}\n\n"
            f"{budget_line}\n"
            "下面是已经写好的正文，请**直接无缝续写后续情节**（不要重复已有内容、"
            "不要复述前文、不要写'续：'之类标记），把本章补足到目标字数，保持同一"
            "风格、人称与时态：\n\n"
            f"{content}"
        )
        try:
            result = generate_with_openrouter(
                system_prompt=system_prompt,
                user_prompt=continuation_prompt,
                preferred_keywords=["qwen", "mistral", "gemini"],
                stream=True,
                on_delta=on_delta or (lambda _c: None),
                role="creator",
            )
        except Exception:
            break
        addition = extract_message_content(result.get("completion")).strip()
        if not addition or addition in content:
            break
        content = f"{content}\n\n{addition}"
        new_total = count_words(content)
        if new_total <= current:
            break
        current = new_total
    return content


def _parse_json_safely(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response text."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    import re

    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return {"raw_response": text[:500], "parse_error": True}


def _persist_chapter_from_content(
    db: Session,
    project_id: int,
    chapter_plan: dict,
    content: str,
    model_id: str,
    book_id: int | None = None,
) -> Any:
    """Create a Chapter record with generated content."""
    from app.services.writing_constraints_service import count_words

    word_count = count_words(content)
    chapter = get_chapter(db, project_id, chapter_plan.get("id"))
    if chapter is None:
        chapter = create_chapter(
            db,
            project_id,
            ChapterCreate(
                chapter_no=int(chapter_plan.get("chapter_no", 1)),
                title=chapter_plan.get("title", ""),
                summary=chapter_plan.get("theme", ""),
                objective=chapter_plan.get("theme", ""),
                conflict="待细化",
                status="drafted",
                draft_content=content,
                final_content=content,
                word_count=word_count,
                version=1,
            ),
        )
    else:
        chapter.draft_content = content
        chapter.final_content = content
        chapter.word_count = word_count
        chapter.status = "drafted"
        chapter.version = (chapter.version or 1) + 1
        db.add(chapter)
        db.commit()
        db.refresh(chapter)

    # 把当前 book_id 写到 chapter（如 chapter.book_id 尚未设置）
    if book_id is not None and getattr(chapter, "book_id", None) is None:
        try:
            chapter.book_id = book_id
            db.add(chapter)
            db.commit()
            db.refresh(chapter)
        except Exception as exc:  # noqa: BLE001 - book_id 写入失败不影响主流程
            logger.warning("set chapter.book_id failed: %s", exc)

    return chapter
