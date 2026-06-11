"""Novel Orchestrator Service - 顶层小说编排服务

三阶段架构：
  Phase 1: Novel Planner — AI 生成完整小说大纲
  Phase 2: Chapter Loop  — 逐章调用现有 workflow 生成正文
  Phase 3: Novel Reviewer — 完成后一致性审查（占位）
"""

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.ai_task import TaskLog
from app.models.character import Character
from app.models.book import Book
from app.models.chapter import Chapter
from app.models.plot_line import PlotLine
from app.schemas.chapter import ChapterCreate
from app.schemas.character import CharacterCreate
from app.schemas.plot_line import PlotLineCreate
from app.schemas.task_runtime import TaskStepStatusUpdate
from app.services.agent_event_bus import AgentEvent, bus, publish_text_delta
from app.services.book_service import get_default_book
from app.services.chapter_loop_service import execute_chapter_with_subagents
from app.services.chapter_service import create_chapter, get_chapter
from app.services.character_service import create_character
from app.services.degradation_service import DegradationLevel, DegradationManager
from app.services.openrouter_service import generate_with_openrouter
from app.services.plot_service import create_plot_line
from app.services.writing_constraints_service import (
    ProjectConstraints,
    build_constraint_block,
    load_project_constraints,
)
from app.services.task_persistence_service import CheckpointData, TaskPersistenceManager
from app.services.task_runtime_service import get_task_runtime_state, set_task_step_runtime_state

logger = logging.getLogger(__name__)


def _event_log_message(event_type: str, phase: str | None, step: str | None, data: dict[str, Any]) -> str:
    chapter_no = data.get("chapter_no")
    title = data.get("title")
    tool = data.get("tool") or data.get("name")
    status = data.get("status")
    if event_type == "phase_start":
        return f"AI 进入阶段：{phase or step or 'unknown'}"
    if event_type == "phase_end":
        return f"AI 完成阶段：{phase or step or 'unknown'}（状态：{status or 'completed'}）"
    if event_type == "step_start" and chapter_no:
        return f"SubAgent 开始撰写第 {chapter_no} 章：{title or ''}".strip()
    if event_type == "step_end" and chapter_no:
        return f"第 {chapter_no} 章执行结束（状态：{status or 'unknown'}，字数：{data.get('word_count', 0)}）"
    if event_type == "tool_call":
        return f"AI 正在调用工具：{tool or phase or step or 'unknown'}"
    if event_type in {"tool_result", "tool_end"}:
        return f"工具返回结果：{tool or phase or step or 'unknown'}（状态：{status or 'success'}）"
    return f"Agent 事件：{event_type}"


def _persist_agent_event(task_id: int, event_type: str, phase: str | None, step: str | None, data: dict[str, Any]) -> None:
    try:
        session = SessionLocal()
        try:
            payload = {
                "event_type": event_type,
                "phase": phase,
                "step": step,
                **data,
            }
            session.add(
                TaskLog(
                    task_id=task_id,
                    step_no=data.get("step_no"),
                    log_type=event_type,
                    message=_event_log_message(event_type, phase, step, data),
                    payload=json.dumps(payload, ensure_ascii=False)[:4000],
                )
            )
            session.commit()
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001 - 日志落库失败不能阻断写作
        logger.debug("Agent event persistence skipped: task_id=%s, err=%s", task_id, exc)


def _honor_runtime_control(project_id: int, task_id: int | None, phase: str, chapter_no: int | None = None) -> bool:
    if task_id is None:
        return True
    pause_announced = False
    while True:
        try:
            runtime = get_task_runtime_state(project_id, task_id)
        except Exception as exc:  # noqa: BLE001
            logger.debug("runtime control read skipped: task_id=%s, err=%s", task_id, exc)
            return True
        if runtime is None or runtime.status in {"running", "pending"}:
            if pause_announced:
                _emit(
                    "tool_result",
                    task_id,
                    phase=phase,
                    tool="runtime_control",
                    status="resumed",
                    chapter_no=chapter_no,
                    message="AI 已收到继续信号，恢复章节循环",
                )
            return True
        if runtime.status == "paused":
            if not pause_announced:
                pause_announced = True
                _emit(
                    "tool_call",
                    task_id,
                    phase=phase,
                    tool="runtime_control",
                    status="paused",
                    chapter_no=chapter_no,
                    message="AI 已暂停，等待继续指令",
                )
                logger.info("Task %s paused by runtime control at chapter %s", task_id, chapter_no)
            time.sleep(2.0)
            continue
        if runtime.status in {"stopped", "cancelling", "cancelled"}:
            _emit(
                "tool_result",
                task_id,
                phase=phase,
                tool="runtime_control",
                status=runtime.status,
                chapter_no=chapter_no,
                message=runtime.message or "AI 收到停止信号，退出章节循环",
            )
            logger.warning("Task %s stopped by runtime control: status=%s", task_id, runtime.status)
            return False
        return True


# ---------------------------------------------------------------------------
# 事件发送辅助
# ---------------------------------------------------------------------------
def _emit(
    event_type: str,
    task_id: int | None,
    *,
    phase: str | None = None,
    step: str | None = None,
    **data: Any,
) -> None:
    """向 AgentEventBus 发布事件。

    仅在 ``task_id`` 存在时发送（向后兼容：未传 task_id 的旧调用方
    不会触发任何事件，避免污染总线）。
    """
    if task_id is None:
        return
    try:
        if event_type not in {"heartbeat", "done", "text_delta"}:
            _persist_agent_event(task_id, event_type, phase, step, data)
        bus.publish(
            AgentEvent(
                event_type=event_type,
                task_id=task_id,
                phase=phase,
                step=step,
                data=data,
            )
        )
    except Exception as emit_exc:  # noqa: BLE001 - 事件总线失败不能影响主流程
        logger.debug("AgentEventBus publish failed: %s", emit_exc)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
NOVEL_LENGTH_RANGES = {
    "short": (10, 30),
    "medium": (30, 100),
    "long": (100, 500),
    "ai_decided": None,  # AI 自行判断
}

DEFAULT_WORD_PER_CHAPTER = 4000

# ---------------------------------------------------------------------------
# JSON 解析辅助
# ---------------------------------------------------------------------------

def _extract_json_from_text(text: object) -> dict:
    """从 LLM 返回的文本中提取 JSON（鲁棒版，支持以下场景）：

    1. 直接合法 JSON
    2. Markdown ```` ```json ... ``` ```` / ```` ``` ... ``` ```` 代码块包裹
    3. 文本中嵌入 JSON（取首 ``{`` 到末 ``}``）
    4. 嵌套的 ``<think>...</think>`` reasoning 残留（DeepSeek / Qwen / Nemotron）
    5. **截断的 JSON**（max_tokens 触顶）：尝试补全未闭合的字符串/数组/对象
    6. trailing comma / Python 风格的 ``None`` / ``True`` / ``False``
    """
    # 防御性检查：非字符串转为字符串
    if not isinstance(text, str):
        if isinstance(text, dict):
            return text
        if isinstance(text, (list, int, float, bool)) or text is None:
            return {"raw_value": text}
        text = str(text)

    # 剥除 reasoning 残留（<think>...</think>），Nemotron / DeepSeek / Qwen 都用这标签
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # 也兼容 特殊标记 <|reasoning|> ... <|/reasoning|>
    text = re.sub(r"<\|reasoning\|>.*?<\|/reasoning\|>", "", text, flags=re.DOTALL)

    text = text.strip()
    if not text:
        raise ValueError("AI 响应为空")

    # 1) 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2) 提取 markdown 代码块
    for pattern in (
        r"```(?:json)?\s*(.*?)\s*```",
        r"`{3,}([^{`].*?)\s*`{3,}",  # 兼容 ``` ... ``` 无语言标签
    ):
        match = re.search(pattern, text, re.DOTALL)
        if match:
            inner = match.group(1).strip()
            # 移除代码块内首行的 ```json 提示
            inner = re.sub(r"^json\s*\n", "", inner)
            try:
                return json.loads(inner)
            except json.JSONDecodeError:
                # 截断代码块：尝试 repair
                repaired = _try_repair_truncated_json(inner)
                if repaired is not None:
                    return repaired

    # 3) 取首 { 到末 } 区间
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            repaired = _try_repair_truncated_json(candidate)
            if repaired is not None:
                return repaired

    # 4) 整体都截断（end == -1 或 end <= start）—— LLM 输出被中途截掉
    # 尝试以第一个 { 开头 repair
    if start != -1:
        repaired = _try_repair_truncated_json(text[start:])
        if repaired is not None:
            return repaired

    raise ValueError(f"无法从 AI 响应中解析 JSON:\n{text[:500]}")


def _try_repair_truncated_json(text: str) -> dict | None:
    """尝试 repair 截断 / 残缺的 JSON 字符串。

    修复策略：
      1. 关闭所有未闭合的双引号（按字符串状态机）
      2. 关闭所有未闭合的 ``[`` ``{``
      3. 移除末尾的 trailing comma

    返回解析后的 dict；失败返回 None。
    """
    if not text:
        return None
    text = text.strip()
    # 移除末尾的 trailing comma
    text = re.sub(r",\s*$", "", text)
    # 把 Python 风格的 None/True/False 转成 JSON 风格
    text = re.sub(r"\bNone\b", "null", text)
    text = re.sub(r"\bTrue\b", "true", text)
    text = re.sub(r"\bFalse\b", "false", text)

    # 字符串状态机：扫描到末尾，关闭所有未闭合的字符串 + 容器
    output: list[str] = []
    in_string = False
    escape = False
    stack: list[str] = []  # 栈：每个元素是 ``"`` / ``[`` / ``{`` 的类型
    for ch in text:
        output.append(ch)
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if in_string:
            if ch == '"':
                in_string = False
                if stack and stack[-1] == '"':
                    stack.pop()
            continue
        if ch == '"':
            in_string = True
            stack.append('"')
        elif ch in "[{":
            stack.append(ch)
        elif ch in "]}":
            if stack and stack[-1] == ch:
                stack.pop()

    # 关闭未闭合的字符串
    if in_string:
        # 字符串里最后一个引号/换行截断 —— 直接补一个 "
        output.append('"')
        if stack and stack[-1] == '"':
            stack.pop()

    # 关闭未闭合的容器（倒序闭合）
    closing = {
        '"': '"',
        '[': ']',
        '{': '}',
    }
    while stack:
        top = stack.pop()
        output.append(closing[top])

    repaired = "".join(output)
    # 移除补完后仍可能存在的 trailing comma
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


def _summarize(value: object, limit: int = 200) -> str:
    text = str(value)
    return " ".join(text.split())[:limit]


# ---------------------------------------------------------------------------
# 章节小结（Chapter Scenes）拆解
# ---------------------------------------------------------------------------
_CHAPTER_TAG = "chapter_scene_for:"


def _inject_chapter_tag(goal: str | None, chapter_id: int) -> str:
    if not goal:
        return f"{_CHAPTER_TAG}{chapter_id}"
    cleaned = re.sub(rf"{_CHAPTER_TAG}\d+\s*", "", goal).strip()
    return f"{_CHAPTER_TAG}{chapter_id} {cleaned}".strip()


def _parse_scene_characters(value: object) -> str | None:
    """从 LLM 返回的 characters_present 字段中规范化为字符串。"""
    if value is None:
        return None
    if isinstance(value, list):
        names = [str(v).strip() for v in value if str(v).strip()]
        return str(names) if names else None
    text = str(value).strip()
    return text or None


def _fallback_split_scenes(content: str, max_scenes: int = 5) -> list[dict]:
    """规则兜底：按 ``\\n\\n`` 段拆分，最多 ``max_scenes`` 个 scene。"""
    paragraphs = [p.strip() for p in (content or "").split("\n\n") if p.strip()]
    if not paragraphs:
        return []
    # 每段合并到 ~3 段一个 scene
    bucket_size = max(1, len(paragraphs) // max_scenes)
    scenes: list[dict] = []
    for i in range(0, len(paragraphs), bucket_size):
        chunk = paragraphs[i : i + bucket_size]
        combined = " ".join(chunk)[:300]
        scenes.append({
            "scene_no": len(scenes) + 1,
            "title": f"场景 {len(scenes) + 1}",
            "summary": combined,
            "goal": None,
            "conflict": None,
            "characters_present": [],
            "emotional_tone": None,
            "status": "completed",
        })
    return scenes[:max_scenes]


def decompose_chapter_into_scenes(
    db: Session,
    chapter: Chapter,
    task_id: int | None = None,
) -> list[PlotLine]:
    """章节生成完成后，把正文拆成 3-7 个 scene 写入 ``plot_lines`` 表。

    策略：
      1. 优先调用 LLM 抽取（JSON 数组，每项含 scene_no/title/summary/...）
      2. LLM 失败时按段落规则兜底

    返回创建的 PlotLine 列表（已 commit）。
    """
    content = (chapter.final_content or chapter.draft_content or "").strip()
    if not content:
        logger.debug(
            "[scene-decompose] chapter %s has no content, skip", chapter.chapter_no
        )
        return []

    # 删除该章节已有 scene（幂等）
    existing = list(
        db.scalars(
            select(PlotLine).where(
                PlotLine.project_id == chapter.project_id,
                PlotLine.plot_type == "chapter_scene",
            )
        )
    )
    for p in existing:
        if p.goal and f"{_CHAPTER_TAG}{chapter.id}" in p.goal:
            db.delete(p)
    db.flush()

    scenes: list[dict] = []

    # --- 1) LLM 抽取 ---
    try:
        system_prompt = (
            "你是一位小说编辑。请将给定的章节正文拆分为 3 到 7 个场景（scene），"
            "每个 scene 描述一段相对完整的情节片段。"
            "仅输出 **纯 JSON 数组**，不要输出任何解释文字。\n"
            "数组中每项的 schema：\n"
            "{\n"
            '  "scene_no": 1,\n'
            '  "title": "场景标题（8-20 字）",\n'
            '  "summary": "1-2 句场景摘要",\n'
            '  "goal": "本场景主要角色的目标（可空）",\n'
            '  "conflict": "本场景的核心冲突（可空）",\n'
            '  "characters_present": ["角色1", "角色2"],\n'
            '  "emotional_tone": "本场景情绪基调（如 紧张 / 悲怆 / 激昂 / 舒缓）",\n'
            '  "status": "completed"\n'
            "}"
        )
        # 只取前 6000 字避免 prompt 过长
        truncated = content[:6000]
        user_prompt = f"章节标题：{chapter.title or f'第{chapter.chapter_no}章'}\n\n章节正文：\n{truncated}"

        _emit(
            "tool_call", task_id, phase="scene_decompose",
            tool="llm_generate",
            chapter_id=chapter.id,
            chapter_no=chapter.chapter_no,
            prompt_chars=len(system_prompt) + len(user_prompt),
        )
        llm_start = time.perf_counter()
        result = generate_with_openrouter(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            stream=True,
            on_delta=lambda c: publish_text_delta(task_id, "scene_decompose", "scene_decompose", c),
            role="controller",
        )
        latency_ms = int((time.perf_counter() - llm_start) * 1000)
        _emit(
            "tool_result", task_id, phase="scene_decompose",
            tool="llm_generate",
            status="success",
            latency_ms=latency_ms,
        )

        completion_raw = result.get("completion", "")
        if isinstance(completion_raw, dict):
            choices = completion_raw.get("choices", [])
            content_text = choices[0].get("message", {}).get("content", "") if choices else ""
        else:
            content_text = str(completion_raw)

        parsed = _extract_json_from_text(content_text)
        if isinstance(parsed, dict) and "scenes" in parsed:
            parsed = parsed["scenes"]
        if isinstance(parsed, list):
            scenes = [s for s in parsed if isinstance(s, dict)]
    except Exception as exc:
        logger.warning(
            "[scene-decompose] LLM 抽取失败，回退到规则拆分: %s", exc
        )
        _emit(
            "tool_result", task_id, phase="scene_decompose",
            tool="llm_generate", status="failed",
            error=str(exc)[:200],
        )

    # --- 2) 规则兜底 ---
    if not scenes:
        scenes = _fallback_split_scenes(content, max_scenes=5)

    # --- 3) 持久化 ---
    created: list[PlotLine] = []
    for idx, sc in enumerate(scenes, 1):
        try:
            scene_no = int(sc.get("scene_no") or idx)
        except (TypeError, ValueError):
            scene_no = idx
        title = (sc.get("title") or f"场景 {scene_no}")[:200]
        summary = sc.get("summary")
        goal_raw = sc.get("goal")
        conflict = sc.get("conflict")
        characters = _parse_scene_characters(sc.get("characters_present"))
        status = sc.get("status") or "completed"

        # chapter_id 暂存到 goal 字段前缀（保持向后兼容，幂等清理时也用这个 tag）；
        # 同时在 summary 中附加一个 JSON 形式 ``chapter_id=N|book_id=M`` 备注供前端解析。
        meta_note = f"[chapter_id={chapter.id}|book_id={chapter.book_id}]"
        goal_with_meta = _inject_chapter_tag(goal_raw, chapter.id)
        if meta_note not in (summary or ""):
            summary = f"{summary or ''} {meta_note}".strip()

        plot = PlotLine(
            project_id=chapter.project_id,
            book_id=chapter.book_id,
            chapter_id=chapter.id,
            title=title,
            plot_type="chapter_scene",
            summary=summary,
            goal=goal_with_meta,
            conflict=conflict,
            stakes=characters,
            status=status if status in ("planned", "in_progress", "completed") else "completed",
            priority=scene_no,
            scene_order=scene_no,
        )
        db.add(plot)
        created.append(plot)
    db.commit()
    for p in created:
        db.refresh(p)

    _emit(
        "tool_result", task_id, phase="scene_decompose",
        tool="decompose_chapter_into_scenes",
        chapter_id=chapter.id,
        chapter_no=chapter.chapter_no,
        scenes_count=len(created),
    )
    logger.info(
        "[scene-decompose] chapter %s 拆解完成: %d scenes",
        chapter.chapter_no, len(created),
    )
    return created


def _run_post_chapter_scene_decomposition(
    db: Session,
    project_id: int,
    chapter_no: int,
    task_id: int | None = None,
) -> int:
    """章节完成后的 scene 拆解钩子：从 DB 拉取已持久化 Chapter 并调用
    ``decompose_chapter_into_scenes``。返回写入的 scene 数量；失败时吞掉异常
    并返回 0（不打断主流程）。
    """
    try:
        chapter = get_chapter(db, project_id, chapter_no)
        if chapter is None:
            logger.debug(
                "[scene-decompose hook] chapter not found: project_id=%s, chapter_no=%s",
                project_id,
                chapter_no,
            )
            return 0
        scenes = decompose_chapter_into_scenes(db, chapter, task_id)
        return len(scenes)
    except Exception as exc:
        logger.warning(
            "[scene-decompose hook] failed: project_id=%s, chapter_no=%s, err=%s",
            project_id,
            chapter_no,
            _summarize(str(exc), 200),
        )
        return 0


# ---------------------------------------------------------------------------
# Phase 0: Web Research（真实联网调研，喂给 Planner）
# ---------------------------------------------------------------------------

def research_topic_via_web(
    db: Session,
    project_id: int,
    topic: str,
    task_id: int | None = None,
) -> dict[str, Any]:
    """联网调研题材趋势（Tavily 搜索 + Firecrawl 抓取），结果喂给大纲规划。

    - 向 AgentEventBus 发送 tool_call/tool_result 事件（前端展示"联网搜索"）。
    - 永不硬失败：搜索不可用时回退到内置趋势关键词，保证主流程继续。
    返回 ``{"summary": str, "keywords": [...], "directions": [...], "sources": [...]}``。
    """
    _emit(
        "tool_call", task_id, phase="research",
        tool="web_search", query=_summarize(topic, 80),
        message=f"联网检索题材趋势：{_summarize(topic, 60)}",
    )
    search_start = time.perf_counter()
    keywords: list[str] = []
    directions: list[dict] = []
    sources: list[dict] = []
    try:
        from app.services.trend_service import execute_trend_exploration

        trend = execute_trend_exploration(
            db,
            project_id=project_id,
            title=f"题材调研: {_summarize(topic, 40)}",
            query_text=topic,
            source_scope="web",
            search_depth="advanced",
            max_results=5,
            allow_builtin_fallback=True,
        )
        try:
            keywords = json.loads(trend.extracted_tags or "[]")[:12]
        except Exception:  # noqa: BLE001
            keywords = []
        try:
            directions = json.loads(trend.suggested_directions or "[]")[:5]
        except Exception:  # noqa: BLE001
            directions = []
        try:
            topics = json.loads(trend.extracted_topics or "[]")
            for t in topics[:5]:
                if isinstance(t, dict):
                    sources.append({
                        "title": t.get("title", ""),
                        "url": t.get("url", ""),
                        "insight": _summarize(t.get("insight", ""), 160),
                    })
        except Exception:  # noqa: BLE001
            sources = []
        _emit(
            "tool_result", task_id, phase="research",
            tool="web_search", status="success",
            latency_ms=int((time.perf_counter() - search_start) * 1000),
            results=len(sources), keywords=len(keywords),
            trend_id=trend.id,
        )
    except Exception as exc:  # noqa: BLE001 - 调研失败不阻断创作
        logger.warning("Web research failed (non-blocking): %s", exc)
        _emit(
            "tool_result", task_id, phase="research",
            tool="web_search", status="failed",
            latency_ms=int((time.perf_counter() - search_start) * 1000),
            error=str(exc)[:200],
        )

    summary_parts: list[str] = []
    if keywords:
        summary_parts.append("热门题材关键词：" + "、".join(str(k) for k in keywords))
    for d in directions:
        if isinstance(d, dict) and d.get("title"):
            premise = _summarize(d.get("premise", ""), 120)
            summary_parts.append(f"方向《{d['title']}》：{premise}")
    summary = "\n".join(summary_parts)
    return {"summary": summary, "keywords": keywords, "directions": directions, "sources": sources}


# ---------------------------------------------------------------------------
# Phase 1: Novel Planner
# ---------------------------------------------------------------------------

def _build_planner_system_prompt() -> str:
    return (
        "你是一位资深的网络小说策划编辑，擅长根据用户给出的题材方向，"
        "规划出结构完整、节奏紧凑的长篇小说大纲。\n\n"
        "你的任务是输出 **纯 JSON**（不要包含任何解释性文字），"
        "JSON 结构如下：\n"
        "{\n"
        '  "title": "小说标题（AI 最终定名）",\n'
        '  "genre": "题材类型（如玄幻/都市/科幻/悬疑等）",\n'
        '  "target_chapters": 50,\n'
        '  "total_estimated_words": 200000,\n'
        '  "chapters": [\n'
        "    {\n"
        '      "chapter_no": 1,\n'
        '      "title": "第一章标题",\n'
        '      "theme": "本章主题",\n'
        '      "word_target": 4000,\n'
        '      "key_events": ["事件1", "事件2"],\n'
        '      "characters_involved": ["角色1", "角色2"]\n'
        "    }\n"
        "  ],\n"
        '  "main_characters": [\n'
        '    {"name": "角色名", "role": "protagonist/antagonist/supporting", "arc": "角色弧线描述"}\n'
        "  ]\n"
        "}\n\n"
        "要求：\n"
        "1. chapters 数组包含所有计划章节\n"
        "2. main_characters 至少包含 3 个主要角色\n"
        "3. 每个章节的 key_events 至少包含 1 个事件\n"
        "4. 根据 novel_length 决定章节数量范围：short=10-30, medium=30-100, long=100-500\n"
        "5. 如果 novel_length 为 ai_decided，根据题材复杂度自行决定章节数量\n"
        "6. 只输出 JSON，不要输出其他任何内容"
    )


def _get_current_book(
    db: Session,
    project_id: int,
    book_id: int | None = None,
) -> Book | None:
    """获取当前创作的"书"。优先取 ``book_id``，否则取默认书（保证每个 project
    至少 1 本书）。

    返回 ``Book`` 行或 ``None``（项目下确实无书时）。
    """
    try:
        if book_id is not None:
            book = db.get(Book, book_id)
            if book is not None and book.project_id == project_id:
                return book
        return get_default_book(db, project_id)
    except Exception as exc:  # noqa: BLE001 - 失败回退到默认书
        logger.debug("get_current_book failed: %s", exc)
        return get_default_book(db, project_id)


def _build_planner_user_prompt(
    topic: str,
    novel_length: str,
    length_range: tuple[int, int] | None,
    book: Book | None = None,
    constraints: ProjectConstraints | None = None,
) -> str:
    length_hint = ""
    if length_range:
        length_hint = f"建议章节数量范围：{length_range[0]}-{length_range[1]} 章。"
    else:
        length_hint = "请根据题材复杂度自行决定章节数量。"

    book_line = ""
    if book is not None:
        book_line = f"当前书名：{book.name} (book_id={book.id})\n"

    constraint_lines = ""
    chapter_count_line = ""
    word_line = ""
    if constraints is not None:
        # 大纲层不需要逐章字数反馈，故关闭 word budget，单独给出每章字数区间提示
        constraint_lines = build_constraint_block(constraints, include_word_budget=False) + "\n\n"
        word_line = (
            f"每章字数必须落在 {constraints.min_words_per_chapter}–"
            f"{constraints.max_words_per_chapter} 字之间，请据此为每章设置合理的 word_target。\n"
        )
        if constraints.target_chapters:
            chapter_count_line = (
                f"用户期望总章节数约为 {constraints.target_chapters} 章，请尽量贴近。\n"
            )

    return (
        f"{constraint_lines}"
        f"请根据以下题材方向规划一部完整的小说大纲：\n\n"
        f"题材方向：{topic}\n"
        f"篇幅偏好：{novel_length}\n"
        f"{length_hint}\n"
        f"{chapter_count_line}"
        f"{word_line}"
        f"{book_line}\n"
        f"请输出符合要求的 JSON 大纲。"
    )


def _normalize_chapter_count(novel_length: str, ai_count: int) -> int:
    """确保章节数量在合理范围内。"""
    bounds = NOVEL_LENGTH_RANGES.get(novel_length)
    if bounds is None:
        # ai_decided: AI 自行判断，但限制在 10-500
        return max(10, min(ai_count, 500))
    low, high = bounds
    return max(low, min(ai_count, high))


def plan_novel_outline(
    db: Session,
    project_id: int,
    topic: str,
    novel_length: str = "ai_decided",
    task_id: int | None = None,
    book_id: int | None = None,
) -> dict:
    """Phase 1: AI 生成完整小说大纲。

    返回结构化的大纲字典，包含 chapters 和 main_characters。
    ``task_id`` 可选：传入后会在关键节点向 ``AgentEventBus`` 发送事件。
    ``book_id`` 可选：传入后会在 prompt 注入当前书名，并写回 ``main_plot_line``
    的 ``book_id``。
    """
    length_range = NOVEL_LENGTH_RANGES.get(novel_length)
    current_book = _get_current_book(db, project_id, book_id)
    book_name = current_book.name if current_book else "默认书"
    book_id_for_records = current_book.id if current_book else None
    constraints = load_project_constraints(db, project_id)

    logger.info(
        "Phase 1 [Novel Planner]: project_id=%s, topic=%s, length=%s, book=%s",
        project_id,
        _summarize(topic, 60),
        novel_length,
        book_name,
    )

    # Phase 1 入口事件
    _emit("phase_start", task_id, phase="planner",
          novel_length=novel_length, project_id=project_id,
          book_id=book_id_for_records, book_name=book_name)

    # Phase 0: 联网调研题材趋势，结果注入规划 prompt（真实 websearch）
    research = research_topic_via_web(db, project_id, topic, task_id=task_id)

    system_prompt = _build_planner_system_prompt()
    user_prompt = _build_planner_user_prompt(
        topic, novel_length, length_range, current_book, constraints
    )
    if research.get("summary"):
        user_prompt = (
            f"{user_prompt}\n\n"
            "【联网调研参考（来自实时网络搜索，请结合当下读者口味与热门元素规划）】\n"
            f"{research['summary']}\n"
        )

    # LLM 调用前：tool_call 事件
    full_prompt = system_prompt + user_prompt
    _emit(
        "tool_call", task_id, phase="planner",
        tool="llm_generate",
        prompt_chars=len(full_prompt),
        model="openrouter-fallback",
    )

    llm_start = time.perf_counter()
    try:
        result = generate_with_openrouter(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            stream=True,
            on_delta=lambda c: publish_text_delta(task_id, "planner", "planner", c),
            role="controller",
        )
    except Exception as llm_exc:
        # LLM 失败也要把 tool_result 失败信息 emit 出去
        _emit(
            "tool_result", task_id, phase="planner",
            tool="llm_generate",
            status="failed",
            latency_ms=int((time.perf_counter() - llm_start) * 1000),
            error=str(llm_exc)[:300],
        )
        raise

    # LLM 响应：tool_result 事件（携带 latency / token 估算 / 实际 model）
    latency_ms = int((time.perf_counter() - llm_start) * 1000)
    model_info = result.get("model") or {}
    model_id = model_info.get("id") if isinstance(model_info, dict) else None
    try:
        from app.services.openrouter_service import _estimate_tokens  # type: ignore
        tokens_estimate = _estimate_tokens(full_prompt, result.get("completion", ""))
    except Exception:
        tokens_estimate = max(0, len(full_prompt) // 4)
    _emit(
        "tool_result", task_id, phase="planner",
        tool="llm_generate",
        status="success",
        latency_ms=latency_ms,
        tokens=tokens_estimate,
        model=model_id or "unknown",
        fallback_used=bool(result.get("fallback_used", False)),
    )

    # completion 是 OpenAI 格式的 dict，需要提取 message.content
    completion_raw = result.get("completion", "")
    if isinstance(completion_raw, dict):
        choices = completion_raw.get("choices", [])
        if choices and isinstance(choices, list):
            message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            completion = message.get("content", "")
        else:
            completion = ""
    else:
        completion = str(completion_raw)

    outline = _extract_json_from_text(completion)

    # 验证并标准化
    if "chapters" not in outline or not isinstance(outline["chapters"], list):
        raise ValueError("AI 大纲缺少 chapters 数组")
    if "main_characters" not in outline or not isinstance(outline["main_characters"], list):
        raise ValueError("AI 大纲缺少 main_characters 数组")

    raw_count = len(outline["chapters"])
    normalized_count = _normalize_chapter_count(novel_length, raw_count)

    # 截断或保持
    outline["chapters"] = outline["chapters"][:normalized_count]
    # 确保 chapter_no 从 1 递增，并把每章 word_target 夹到项目字数区间内，
    # 让"用户设定字数"真正约束到每一章。
    for i, ch in enumerate(outline["chapters"], 1):
        ch["chapter_no"] = i
        raw_target = ch.get("word_target") or constraints.word_target
        try:
            raw_target = int(raw_target)
        except (TypeError, ValueError):
            raw_target = constraints.word_target
        ch["word_target"] = max(
            constraints.min_words_per_chapter,
            min(raw_target, constraints.max_words_per_chapter),
        )
        ch.setdefault("key_events", [])
        ch.setdefault("characters_involved", [])

    outline["target_chapters"] = normalized_count
    outline["total_estimated_words"] = sum(
        ch.get("word_target", DEFAULT_WORD_PER_CHAPTER) for ch in outline["chapters"]
    )

    # 保存到数据库：创建 PlotLine（主线剧情）
    main_plot_title = f"{outline.get('title', '未命名')} - 主线剧情"
    main_plot = create_plot_line(
        db,
        project_id,
        PlotLineCreate(
            title=main_plot_title,
            plot_type="novel_outline_main",
            summary=outline.get("genre", ""),
            goal=f"完成 {normalized_count} 章小说创作",
            conflict="待生成",
            stakes="小说项目整体质量",
            start_phase="novel_planner",
            end_phase="novel_reviewer",
            status="planned",
            priority=1,
        ),
    )
    if book_id_for_records is not None and getattr(main_plot, "book_id", None) is None:
        main_plot.book_id = book_id_for_records
        db.add(main_plot)
        db.commit()
        db.refresh(main_plot)
    outline["main_plot_line_id"] = main_plot.id
    outline["book_id"] = book_id_for_records
    outline["book_name"] = book_name

    # 保存主要角色
    created_characters = []
    for char_info in outline.get("main_characters", [])[:10]:  # 最多 10 个
        name = char_info.get("name", "未命名角色")
        role = char_info.get("role", "supporting")
        arc = char_info.get("arc", "")
        created_characters.append(
            create_character(
                db,
                project_id,
                CharacterCreate(
                    name=name,
                    role_type=role,
                    arc_summary=arc,
                    motivation="由 Novel Planner 生成",
                    goal="待细化",
                    status="active",
                    book_id=book_id_for_records,
                ),
            )
        )
    outline["created_characters"] = created_characters

    logger.info(
        "Phase 1 completed: title=%s, chapters=%d, characters=%d, plot_line_id=%s",
        outline.get("title", ""),
        normalized_count,
        len(created_characters),
        main_plot.id,
    )

    # Phase 1 出口事件
    _emit(
        "phase_end", task_id, phase="planner",
        title=outline.get("title", ""),
        chapters=len(outline.get("chapters", [])),
        characters=len(created_characters),
        total_estimated_words=outline.get("total_estimated_words", 0),
    )

    return outline


# ---------------------------------------------------------------------------
# Resume-from-checkpoint
# ---------------------------------------------------------------------------

def _load_chapter_plans_from_db(
    db: Session,
    project_id: int,
    from_chapter: int,
) -> list[dict]:
    """从数据库中加载已存在的章节行，构建最小章节计划列表。

    用于 resume 场景：原始工作流的 Phase 1 大纲只在内存中，
    DB 中只能拿到已创建/已完成的 Chapter 行。这里把它们转换成
    ``ch_plan`` 字典供 ``_execute_chapter_loop`` 继续迭代。
    """
    existing = db.scalars(
        select(Chapter)
        .where(Chapter.project_id == project_id, Chapter.chapter_no >= from_chapter)
        .order_by(Chapter.chapter_no.asc())
    ).all()
    plans: list[dict] = []
    for ch in existing:
        plans.append({
            "chapter_no": ch.chapter_no,
            "title": ch.title or f"第{ch.chapter_no}章",
            "theme": ch.objective or ch.summary or "",
            "word_target": ch.word_count or DEFAULT_WORD_PER_CHAPTER,
            "key_events": [],
            "characters_involved": [],
        })
    return plans


def _detect_resume_checkpoint(db: Session, project_id: int, outline: dict) -> int:
    """检测断点：返回第一个未完成章节的 chapter_no。

    检查数据库中已存在的章节，跳过已有 final_content 的章节。
    如果所有章节都已完成，返回 outline 最大 chapter_no + 1（表示全部完成）。
    """
    chapters = outline.get("chapters", [])
    if not chapters:
        return 1

    # 查询数据库中该项目的所有章节
    existing = db.scalars(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_no.asc())
    ).all()

    # 构建 chapter_no -> final_content 映射
    completed_chapters: set[int] = set()
    for ch in existing:
        if ch.final_content:
            completed_chapters.add(ch.chapter_no)

    # 找到第一个未完成的章节
    for ch_plan in chapters:
        ch_no = ch_plan.get("chapter_no", 0)
        if ch_no not in completed_chapters:
            logger.info(
                "Resume checkpoint: chapter %d is the first incomplete (found %d completed in DB)",
                ch_no,
                len(completed_chapters),
            )
            return ch_no

    # 所有章节都已完成
    last_no = max((ch.get("chapter_no", 0) for ch in chapters), default=0)
    logger.info(
        "Resume checkpoint: all %d chapters already completed in DB",
        len(completed_chapters),
    )
    return last_no + 1



def _call_chapter_with_transient_retry(
    db: Session,
    project_id: int,
    chapter_plan: dict,
    novel_outline: dict,
    previous_chapters_context: str,
    **kwargs: Any,
) -> dict:
    """对 ``execute_chapter_with_subagents`` 做瞬时错误重试包装。

    仅重试 ``httpx.ReadTimeout`` / ``httpx.ConnectError`` 与 5xx
    ``HTTPStatusError``；非瞬时错误（如 4xx）直接抛出。
    重试 1 次后仍失败则把最后一次异常抛给上层
    ``DegradationManager`` 处理分级降级。
    """
    try:
        from httpx import ReadTimeout, ConnectError, HTTPStatusError
    except Exception:  # pragma: no cover - httpx 应当已安装
        ReadTimeout = ConnectError = HTTPStatusError = Exception  # type: ignore

    ch_no = chapter_plan.get("chapter_no", "?")
    last_exc: Exception | None = None
    for attempt in (1, 2):
        try:
            result = execute_chapter_with_subagents(
                db=db,
                project_id=project_id,
                chapter_plan=chapter_plan,
                novel_outline=novel_outline,
                previous_chapters_context=previous_chapters_context,
                task_id=kwargs.get("task_id") if isinstance(kwargs, dict) else None,
                book_id=kwargs.get("book_id") if isinstance(kwargs, dict) else None,
                book_name=kwargs.get("book_name") if isinstance(kwargs, dict) else None,
            )
            return result
        except (ReadTimeout, ConnectError) as exc:
            last_exc = exc
            logger.warning(
                "chapter %s transient failure (attempt %d/2): %s",
                ch_no,
                attempt,
                exc,
            )
            if attempt == 1:
                time.sleep(2)
                continue
            break
        except HTTPStatusError as exc:
            # 仅 5xx 视为瞬时错误触发重试
            status_code = getattr(getattr(exc, "response", None), "status_code", 0) or 0
            if status_code < 500:
                raise
            last_exc = exc
            logger.warning(
                "chapter %s transient 5xx (attempt %d/2, status=%s): %s",
                ch_no,
                attempt,
                status_code,
                exc,
            )
            if attempt == 1:
                time.sleep(2)
                continue
            break
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# Phase 2: Chapter Loop
# ---------------------------------------------------------------------------

def _execute_chapter_loop(
    db: Session,
    project_id: int,
    outline: dict,
    start_chapter: int = 1,
    max_chapters: int | None = None,
    style_hint: str | None = None,
    revision_focus: str | None = None,
    task_id: int | None = None,
    accumulated_context: dict | None = None,
) -> dict:
    """Phase 2: SubAgent 驱动章节循环创作。

    使用 LangGraph DAG + SubAgent 并行执行（替代旧线性 workflow）：
    1. Planner → [Character Agent, Plot Agent, Worldbook Agent]（并行）
    2. Writer → Reviewer → Reviser（条件分支）

    支持：
    - 从指定章节开始（断点续跑）
    - 限制最大章节数（测试用）
    - DegradationManager 管理的分级降级与重试策略
    - 上下文累积（前文摘要、角色档案、剧情脉络）
    - 进度追踪
    - 通过 ``accumulated_context`` 从检查点恢复时种入历史摘要/角色档案
    """
    chapters = outline.get("chapters", [])
    if max_chapters:
        chapters = chapters[:max_chapters]

    total = len(chapters)
    completed = 0
    failed = 0
    skipped = 0
    total_words = 0
    chapter_results = []
    errors = []

    # 创建 DegradationManager
    degradation_mgr = DegradationManager()

    # 上下文累积：前几章摘要（用于后续章节的 previous_chapters_context）
    previous_chapters_summary: list[str] = []
    # 角色档案累积：角色名 → 最新状态描述
    character_profiles: dict[str, str] = {}
    # 作者实时指示累积（通过 /tasks/{id}/message 发送，逐章注入写作上下文）
    user_directives: list[str] = []

    # 从 accumulated_context 恢复上下文（resume 场景）
    if accumulated_context:
        previous_chapters_summary = list(accumulated_context.get("previous_chapters_summary") or [])
        character_profiles = dict(accumulated_context.get("character_profiles") or {})
        logger.info(
            "Phase 2 [Chapter Loop] restored %d summaries, %d character profiles from accumulated_context",
            len(previous_chapters_summary),
            len(character_profiles),
        )

    logger.info(
        "Phase 2 [Chapter Loop - SubAgent Driven]: %d chapters to process, starting from chapter_no=%s",
        total,
        start_chapter,
    )

    # Phase 2 入口事件
    _emit(
        "phase_start", task_id, phase="chapter_loop",
        total_chapters=total,
        start_chapter=start_chapter,
    )

    for ch_plan in chapters:
        ch_no = ch_plan.get("chapter_no", 0)
        if ch_no < start_chapter:
            continue

        if not _honor_runtime_control(project_id, task_id, "chapter_loop", ch_no):
            chapter_results.append({
                "chapter_no": ch_no,
                "status": "cancelled",
                "error": "运行时控制请求停止",
            })
            break

        # 作者实时指示：每章创作前取出待处理消息，注入写作上下文并回执
        if task_id is not None:
            try:
                from app.services.user_message_registry import user_message_registry

                fresh_directives = user_message_registry.drain(task_id)
                if fresh_directives:
                    user_directives.extend(fresh_directives)
                    _emit(
                        "tool_result", task_id, phase="chapter_loop",
                        tool="user_directive", chapter_no=ch_no,
                        message=f"已采纳作者的 {len(fresh_directives)} 条实时指示，将在本章起生效",
                    )
            except Exception as ud_exc:  # noqa: BLE001
                logger.debug("drain user directives skipped: %s", ud_exc)

        # 细粒度取消检查：每章 LLM 调用前检查取消信号
        from app.api.routes.tasks import task_cancellation_registry
        if task_id is not None and task_cancellation_registry.is_cancelled(task_id):
            logger.warning("[cancellation] cancel signal detected at chapter %d, aborting", ch_no)
            chapter_results.append({
                "chapter_no": ch_no,
                "status": "cancelled",
                "error": "用户请求取消",
            })
            break

        ch_title = ch_plan.get("title", f"第{ch_no}章")
        ch_theme = ch_plan.get("theme", "")
        ch_word_target = ch_plan.get("word_target", DEFAULT_WORD_PER_CHAPTER)
        key_events = ch_plan.get("key_events", [])
        characters_involved = ch_plan.get("characters_involved", [])

        logger.info(
            "Phase 2: Processing chapter %d/%d: %s",
            ch_no,
            total,
            ch_title,
        )

        # Phase 2 每章入口事件
        _emit(
            "step_start", task_id, phase="chapter_loop",
            chapter_no=ch_no,
            title=ch_title,
            theme=ch_theme,
            word_target=ch_word_target,
        )

        # 获取当前降级级别
        level = degradation_mgr.get_degradation_level(ch_no)

        if level == DegradationLevel.SKIP:
            # SKIP 级别：跳过本章
            skipped += 1
            last_error = degradation_mgr.get_last_error(ch_no)
            error_info = _summarize(last_error, 300) if last_error else "已达到最大重试次数，跳过"
            errors.append({
                "chapter_no": ch_no,
                "title": ch_title,
                "error": error_info,
                "degradation_level": "SKIP",
            })
            chapter_results.append({
                "chapter_no": ch_no,
                "title": ch_title,
                "status": "skipped",
                "error": error_info,
                "degradation_level": "SKIP",
            })
            logger.warning("Chapter %d SKIPPED (max retries exceeded): %s", ch_no, error_info)

            # SKIP 阶段结束事件
            _emit(
                "step_end", task_id, phase="chapter_loop",
                chapter_no=ch_no,
                status="skipped",
                error=error_info,
                degradation_level="SKIP",
            )

            progress_msg = (
                f"小说生成进度：已完成 {completed}/{total} 章，"
                f"失败 {failed} 章，跳过 {skipped} 章，累计 {total_words} 字"
            )
            logger.info(progress_msg)
            continue

        # 构建前文章节上下文
        previous_context = "\n".join(previous_chapters_summary[-5:])  # 最近 5 章摘要
        if not previous_context:
            previous_context = "这是第一章，无前置上下文。"
        # 注入作者实时指示（优先级最高，放在上下文最前）
        if user_directives:
            directive_block = "【作者实时指示 —— 必须在创作中遵守】\n" + "\n".join(
                f"- {d}" for d in user_directives[-10:]
            )
            previous_context = f"{directive_block}\n\n{previous_context}"

        # 构建 SubAgent 章节计划
        subagent_chapter_plan = {
            "id": ch_plan.get("id"),
            "chapter_no": ch_no,
            "title": ch_title,
            "theme": ch_theme,
            "word_target": ch_word_target,
            "key_events": key_events,
            "characters_involved": characters_involved,
        }

        # 构建小说大纲（供 SubAgent 使用）
        subagent_outline = {
            "title": outline.get("title", ""),
            "genre": outline.get("genre", ""),
            "main_characters": outline.get("main_characters", []),
            "character_profiles": character_profiles,
        }

        # 解析当前 book（plan_novel_outline 已经把 book_id/book_name 塞到 outline）
        outline_book_id = outline.get("book_id")
        outline_book_name = outline.get("book_name")
        if outline_book_id is None or not outline_book_name:
            try:
                _bk = _get_current_book(db, project_id, outline_book_id)
                if _bk is not None:
                    outline_book_id = outline_book_id or _bk.id
                    outline_book_name = outline_book_name or _bk.name
            except Exception:  # noqa: BLE001
                pass

        # 使用 DegradationManager 管理重试
        chapter_ok = False
        chapter_cancelled = False
        last_exc = None
        attempts_used = 0

        while degradation_mgr.should_retry(ch_no):
            if not _honor_runtime_control(project_id, task_id, "chapter_loop", ch_no):
                chapter_cancelled = True
                chapter_results.append({
                    "chapter_no": ch_no,
                    "status": "cancelled",
                    "error": "运行时控制请求停止",
                })
                break

            attempts_used += 1

            # 计算退避延迟
            delay = degradation_mgr.get_backoff_delay(ch_no)
            if delay > 0:
                logger.warning(
                    "Chapter %d retry attempt %d, backing off %.1fs (level=%s)",
                    ch_no,
                    attempts_used,
                    delay,
                    level.name,
                )
                time.sleep(delay)

            try:
                # 调用 SubAgent 驱动的执行器（DAG 并行执行），
                # 包裹一层瞬时错误重试（httpx 5xx / ReadTimeout / ConnectError）
                step_result = _call_chapter_with_transient_retry(
                    db=db,
                    project_id=project_id,
                    chapter_plan=subagent_chapter_plan,
                    novel_outline=subagent_outline,
                    previous_chapters_context=previous_context,
                    task_id=task_id,
                    book_id=outline_book_id,
                    book_name=outline_book_name,
                )

                # 提取结果
                chapter_obj = step_result.get("chapter")
                words = 0
                if chapter_obj:
                    words = getattr(chapter_obj, "word_count", 0) or 0
                    total_words += words

                # 更新前文摘要（取前 300 字作为摘要）
                if chapter_obj:
                    content = getattr(chapter_obj, "final_content", "") or getattr(chapter_obj, "draft_content", "") or ""
                    summary_snippet = content[:300].strip()
                    previous_chapters_summary.append(f"第{ch_no}章《{ch_title}》：{summary_snippet}...")

                # 更新角色档案（从 SubAgent 结果中提取）
                subagent_results = step_result.get("subagent_results", {})
                char_design = subagent_results.get("character_agent", {})
                char_design_data = char_design.get("design", {}) if isinstance(char_design, dict) else {}
                if isinstance(char_design_data, dict):
                    for char_name, char_info in char_design_data.items():
                        if isinstance(char_info, str):
                            character_profiles[char_name] = char_info
                        elif isinstance(char_info, dict):
                            character_profiles[char_name] = str(char_info)[:200]

                chapter_results.append({
                    "chapter_no": ch_no,
                    "title": ch_title,
                    "status": "completed",
                    "word_count": words,
                    "attempts": attempts_used,
                    "degradation_level": level.name,
                    "mode": step_result.get("mode", "unknown"),
                    "consistency_report": str(step_result.get("consistency_report", ""))[:200],
                })
                completed += 1
                chapter_ok = True

                logger.info(
                    "Chapter %d completed: %d words, %d attempt(s), level=%s, mode=%s",
                    ch_no,
                    words,
                    attempts_used,
                    level.name,
                    step_result.get("mode", "unknown"),
                )
                # 章节成功完成事件
                _emit(
                    "step_end", task_id, phase="chapter_loop",
                    chapter_no=ch_no,
                    status="completed",
                    word_count=words,
                    attempts=attempts_used,
                    mode=step_result.get("mode", "unknown"),
                )
                # 章节完成后，异步把章节正文拆成 3-7 个 scene 写入 plot_lines
                try:
                    _run_post_chapter_scene_decomposition(db, project_id, ch_no, task_id)
                except Exception as decomp_exc:
                    logger.warning(
                        "chapter %d scene-decompose failed (non-blocking): %s",
                        ch_no, _summarize(str(decomp_exc), 200),
                    )
                break

            except Exception as exc:
                last_exc = exc
                degradation_mgr.record_failure(ch_no, str(exc))
                logger.error(
                    "Chapter %d attempt %d failed: %s",
                    ch_no,
                    attempts_used,
                    _summarize(str(exc), 300),
                    exc_info=True,
                )

                # 更新降级级别（失败后可能升级为 SIMPLIFIED 或 SKIP）
                level = degradation_mgr.get_degradation_level(ch_no)

        if chapter_cancelled:
            break
        if chapter_ok:
            # 成功后重置状态
            degradation_mgr.reset_chapter(ch_no)
            # 保存检查点（断点续传 + 累积上下文）
            if task_id is not None:
                try:
                    persistence_mgr = TaskPersistenceManager()
                    checkpoint = CheckpointData(
                        task_id=task_id,
                        current_phase="chapter_loop",
                        completed_chapters=[c["chapter_no"] for c in chapter_results if c.get("status") == "completed"],
                        total_chapters=total,
                        last_chapter_no=ch_no,
                        accumulated_context={
                            "previous_chapters_summary": previous_chapters_summary[-10:],
                            "character_profiles": character_profiles,
                            "outline_title": outline.get("title", ""),
                            "outline_genre": outline.get("genre", ""),
                            "book_id": outline.get("book_id"),
                            "book_name": outline.get("book_name"),
                        },
                        failure_history=[
                            {"chapter_no": k, "errors": v.get("errors", [])}
                            for k, v in degradation_mgr.get_summary().items()
                        ],
                    )
                    persistence_mgr.save_task_checkpoint(task_id, checkpoint)
                    logger.info("Checkpoint saved: task_id=%s, completed=%d/%d", task_id, completed, total)
                except Exception as cp_exc:
                    logger.warning("Failed to save checkpoint: %s", cp_exc)
        else:
            failed += 1
            error_info = _summarize(str(last_exc), 300) if last_exc else "未知错误"
            errors.append({
                "chapter_no": ch_no,
                "title": ch_title,
                "error": error_info,
                "degradation_level": level.name,
            })
            chapter_results.append({
                "chapter_no": ch_no,
                "title": ch_title,
                "status": "failed",
                "error": error_info,
                "attempts": attempts_used,
                "degradation_level": level.name,
            })
            logger.error(
                "Chapter %d failed after %d attempt(s), final level=%s: %s",
                ch_no,
                attempts_used,
                level.name,
                error_info,
            )
            # 章节失败事件
            _emit(
                "step_end", task_id, phase="chapter_loop",
                chapter_no=ch_no,
                status="failed",
                error=error_info,
                attempts=attempts_used,
                degradation_level=level.name,
            )

        # 更新项目进度日志
        progress_msg = (
            f"小说生成进度：已完成 {completed}/{total} 章，"
            f"失败 {failed} 章，跳过 {skipped} 章，累计 {total_words} 字"
        )
        logger.info(progress_msg)

    # Phase 2 出口事件
    _emit(
        "phase_end", task_id, phase="chapter_loop",
        total_chapters=total,
        completed=completed,
        failed=failed,
        skipped=skipped,
        total_words=total_words,
    )

    return {
        "total_chapters": total,
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
        "total_words": total_words,
        "chapter_results": chapter_results,
        "errors": errors,
        "degradation_summary": degradation_mgr.get_summary(),
        "accumulated_context": {
            "previous_chapters_summary_count": len(previous_chapters_summary),
            "character_profiles_count": len(character_profiles),
        },
    }


# ---------------------------------------------------------------------------
# Phase 3: Novel Reviewer (占位)
# ---------------------------------------------------------------------------

def _execute_novel_reviewer(
    db: Session,
    project_id: int,
    outline: dict,
    chapter_loop_result: dict,
    task_id: int | None = None,
) -> dict:
    """Phase 3: 小说完成后一致性审查（占位实现）。

    当前仅记录日志和基本信息，后续可扩展为 AI 审查服务。
    ``task_id`` 可选：传入后会在入口 / 出口向 ``AgentEventBus`` 发送事件。
    """
    logger.info(
        "Phase 3 [Novel Reviewer]: project_id=%s, title=%s",
        project_id,
        outline.get("title", ""),
    )

    # Phase 3 入口事件
    _emit("phase_start", task_id, phase="reviewer",
          title=outline.get("title", ""),
          total_chapters=chapter_loop_result.get("total_chapters", 0))

    # 3.1 构建知识图谱：分析已生成的角色 / 剧情 / 世界观，抽取人物关系、
    #     故事弧线、关键事件、主题连接，写入 PostgreSQL 并同步 Neo4j。
    #     这一步让"知识图谱"页面真正有数据（人物关系边 + 事件网络）。
    graph_summary: dict[str, Any] = {"status": "skipped"}
    try:
        from app.services.story_graph_generation_service import generate_normalized_story_graph

        _emit("tool_call", task_id, phase="reviewer", tool="build_knowledge_graph",
              message="开始构建人物关系与事件知识图谱")
        graph_summary = generate_normalized_story_graph(db, project_id, task_id=task_id)
        logger.info("Phase 3 knowledge graph built: %s", graph_summary)
        _emit(
            "tool_result", task_id, phase="reviewer", tool="build_knowledge_graph",
            status=graph_summary.get("status", "completed"),
            relationships=graph_summary.get("added_relationships", 0),
            events=graph_summary.get("added_events", 0),
            arcs=graph_summary.get("added_arcs", 0),
            themes=graph_summary.get("added_themes", 0),
        )
    except Exception as graph_exc:  # noqa: BLE001 - 图谱构建失败不阻断审查
        logger.warning("Phase 3 knowledge graph build failed (non-blocking): %s", graph_exc)
        graph_summary = {"status": "failed", "error": str(graph_exc)[:200]}
        _emit("tool_result", task_id, phase="reviewer", tool="build_knowledge_graph",
              status="failed", error=str(graph_exc)[:200])

    review_result = {
        "status": "completed",
        "title": outline.get("title", ""),
        "total_chapters": chapter_loop_result.get("total_chapters", 0),
        "completed_chapters": chapter_loop_result.get("completed", 0),
        "failed_chapters": chapter_loop_result.get("failed", 0),
        "total_words": chapter_loop_result.get("total_words", 0),
        "knowledge_graph": graph_summary,
        "message": "全文审查完成，知识图谱已更新。",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info("Phase 3 completed: %s", review_result)

    # Phase 3 出口事件
    _emit("phase_end", task_id, phase="reviewer",
          status=review_result.get("status", "unknown"),
          completed_chapters=review_result.get("completed_chapters", 0),
          total_words=review_result.get("total_words", 0),
          graph_relationships=graph_summary.get("added_relationships", 0),
          graph_events=graph_summary.get("added_events", 0))

    return review_result


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def execute_novel_workflow(
    db: Session,
    project_id: int,
    topic: str,
    novel_length: str = "ai_decided",
    style_hint: str | None = None,
    revision_focus: str | None = None,
    start_chapter: int = 1,
    max_chapters: int | None = None,
    skip_planner: bool = False,
    pre_built_outline: dict | None = None,
    task_id: int | None = None,
    accumulated_context: dict | None = None,
    book_id: int | None = None,
    **kwargs: Any,
) -> dict:
    """完整的小说创作工作流入口 —— 替代旧的 execute_auto_novel_workflow。

    参数：
        db: 数据库会话
        project_id: 项目 ID
        topic: 小说题材方向/主题
        novel_length: 篇幅偏好 short/medium/long/ai_decided
        style_hint: 风格提示（可选）
        revision_focus: 修订重点（可选）
        start_chapter: 从第几章开始（支持断点续跑）
        max_chapters: 最大生成章节数（测试用）
        skip_planner: 跳过 Phase 1（使用预构建大纲）
        pre_built_outline: 预构建的大纲（当 skip_planner=True 时使用）
        task_id: 任务 ID（用于取消注册表 + 检查点持久化）
        accumulated_context: 检查点累积上下文；提供时跳过 Phase 1 并把
            previous_chapters_summary / character_profiles 种入 Phase 2
        book_id: 当前创作所属 book（传入后会注入 LLM prompt 并写回 book_id）

    返回：
        包含三个阶段结果的完整字典
    """
    workflow_start = time.perf_counter()
    workflow_id = f"novel_wf_{project_id}_{int(time.time())}"
    final_result: dict[str, Any] = {}
    fail_status: tuple[str, str] | None = None  # (phase, error)

    def _mark_step(step_no: int, step_name: str, status: str, message: str | None = None) -> None:
        """在 Phase 边界把对应 step 的状态写回 DB（之前 steps 表 status 永不更新，
        导致前端 Step 1 永远显示 running）。包 try/except，任何异常都不能阻断工作流。"""
        if task_id is None:
            return
        try:
            set_task_step_runtime_state(
                project_id,
                task_id,
                TaskStepStatusUpdate(
                    step_no=step_no,
                    step_name=step_name,
                    status=status,
                    react_state="observe",
                    message=message,
                ),
                db=db,
            )
        except Exception as ms_exc:  # noqa: BLE001
            logger.debug("mark step %d %s failed (non-blocking): %s", step_no, status, ms_exc)

    logger.info(
        "Novel Orchestrator started: workflow_id=%s, project_id=%s, topic=%s, length=%s, "
        "start_chapter=%s, has_accumulated_context=%s",
        workflow_id,
        project_id,
        _summarize(topic, 60),
        novel_length,
        start_chapter,
        bool(accumulated_context),
    )

    try:
        # Phase 1: Novel Planner
        # 当 accumulated_context 提供时跳过 Phase 1，并从 DB 加载已有章节行构造最小 outline
        if accumulated_context is not None:
            logger.info("Phase 1 skipped: resuming from accumulated_context")
            # BUG B 续跑补丁：resume 路径不走 Phase 1 try 块，所以 1807-1808 行的
            # mark_step(1, completed) / mark_step(2, running) 不会触发。手动补打，
            # 否则前端会一直看到 step 1=running、step 2=pending。
            _mark_step(1, "Novel Planner", "completed", "从检查点恢复（Phase 1 之前已完成）")
            _mark_step(2, "Chapter Generation Loop", "running", f"从第 {start_chapter} 章续跑")
            restored_chapter_plans = _load_chapter_plans_from_db(db, project_id, start_chapter)
            outline = {
                "title": accumulated_context.get("outline_title", topic or "未命名"),
                "genre": accumulated_context.get("outline_genre", ""),
                "chapters": restored_chapter_plans,
                "target_chapters": max(
                    (c["chapter_no"] for c in restored_chapter_plans),
                    default=start_chapter,
                ),
                "main_characters": accumulated_context.get("main_characters", []),
                "book_id": accumulated_context.get("book_id") or book_id,
                "book_name": accumulated_context.get("book_name"),
            }
            # 如果还没拿到 book_name，从 DB 拉一下
            if outline["book_id"] and not outline["book_name"]:
                try:
                    _bk = _get_current_book(db, project_id, outline["book_id"])
                    if _bk is not None:
                        outline["book_name"] = _bk.name
                except Exception:  # noqa: BLE001
                    pass
            skip_planner = True
            pre_built_outline = outline
        elif skip_planner and pre_built_outline:
            logger.info("Phase 1 skipped: using pre-built outline")
            outline = pre_built_outline
            # 补齐 book 信息
            if not outline.get("book_id"):
                outline["book_id"] = book_id
            if outline.get("book_id") and not outline.get("book_name"):
                try:
                    _bk = _get_current_book(db, project_id, outline["book_id"])
                    if _bk is not None:
                        outline["book_name"] = _bk.name
                except Exception:  # noqa: BLE001
                    pass
        else:
            try:
                outline = plan_novel_outline(
                    db=db,
                    project_id=project_id,
                    topic=topic,
                    novel_length=novel_length,
                    task_id=task_id,
                    book_id=book_id,
                )
            except Exception as exc:
                logger.error("Phase 1 [Novel Planner] failed: %s", exc, exc_info=True)
                _emit(
                    "phase_end", task_id, phase="planner",
                    status="failed",
                    error=str(exc)[:300],
                )
                _mark_step(1, "Novel Planner", "failed", _summarize(str(exc), 300))
                fail_status = ("novel_planner", str(exc))
                final_result = {
                    "workflow_id": workflow_id,
                    "status": "failed",
                    "phase": "novel_planner",
                    "error": str(exc)[:500],
                    "elapsed_seconds": time.perf_counter() - workflow_start,
                }
                return final_result

        # Phase 1 完成（成功路径）：step 1 → completed, step 2 → running
        _mark_step(1, "Novel Planner", "completed", "大纲规划完成")
        _mark_step(2, "Chapter Generation Loop", "running", "开始逐章生成")

    # Phase 2: Chapter Loop
        # Phase 2: Chapter Loop
        chapter_loop_start = time.perf_counter()

        # 自动断点检测：如果 start_chapter=1 且使用预构建大纲，检查数据库
        effective_start = start_chapter
        if effective_start == 1 and (skip_planner or pre_built_outline):
            effective_start = _detect_resume_checkpoint(db, project_id, outline)
            if effective_start > 1:
                logger.info(
                    "Auto-resume: starting from chapter %d (found completed chapters in DB)",
                    effective_start,
                )

        try:
            chapter_result = _execute_chapter_loop(
                db=db,
                project_id=project_id,
                outline=outline,
                start_chapter=effective_start,
                max_chapters=max_chapters,
                style_hint=style_hint,
                revision_focus=revision_focus,
                task_id=kwargs.get("task_id") or task_id,
                accumulated_context=accumulated_context,
            )
        except Exception as exc:
            logger.error("Phase 2 [Chapter Loop] failed: %s", exc, exc_info=True)
            _emit(
                "phase_end", task_id, phase="chapter_loop",
                status="failed",
                error=str(exc)[:300],
            )
            _mark_step(2, "Chapter Generation Loop", "failed", _summarize(str(exc), 300))
            fail_status = ("chapter_loop", str(exc))
            final_result = {
                "workflow_id": workflow_id,
                "status": "failed",
                "phase": "chapter_loop",
                "outline": outline,
                "error": str(exc)[:500],
                "elapsed_seconds": time.perf_counter() - workflow_start,
            }
            return final_result

        # Phase 2 完成：step 2 → completed, step 3 → running
        _mark_step(2, "Chapter Generation Loop", "completed", f"完成 {chapter_result.get('completed', 0)}/{chapter_result.get('total_chapters', 0)} 章")
        _mark_step(3, "Novel Reviewer", "running", "开始全文一致性审查")

        # Phase 3: Novel Reviewer
        try:
            review_result = _execute_novel_reviewer(
                db=db,
                project_id=project_id,
                outline=outline,
                chapter_loop_result=chapter_result,
                task_id=task_id,
            )
        except Exception as exc:
            logger.warning("Phase 3 [Novel Reviewer] failed (non-critical): %s", exc)
            _mark_step(3, "Novel Reviewer", "failed", _summarize(str(exc), 300))
            review_result = {
                "status": "error",
                "message": f"Reviewer failed: {str(exc)[:300]}",
            }

        # Phase 3 完成：step 3 → completed（如果 try 成功；失败时上面已 mark failed，
        # 但 Phase 3 是 non-critical，再次覆盖为 completed 以反映"已尝试过"）
        if review_result.get("status") != "error":
            _mark_step(3, "Novel Reviewer", "completed", "全文一致性审查完成")
        else:
            _mark_step(3, "Novel Reviewer", "completed", "Reviewer 失败但已尝试，跳过")

        elapsed = time.perf_counter() - workflow_start

        final_result = {
            "workflow_id": workflow_id,
            "status": "completed" if chapter_result.get("failed", 0) == 0 else "partial",
            "elapsed_seconds": round(elapsed, 2),
            "phases": {
                "novel_planner": {
                    "status": "completed",
                    "title": outline.get("title", ""),
                    "target_chapters": outline.get("target_chapters", 0),
                    "total_estimated_words": outline.get("total_estimated_words", 0),
                },
                "chapter_loop": {
                    "status": "completed",
                    **chapter_result,
                    "elapsed_seconds": round(time.perf_counter() - chapter_loop_start, 2),
                },
                "novel_reviewer": review_result,
            },
            "novel_outline": {
                "title": outline.get("title", ""),
                "genre": outline.get("genre", ""),
                "target_chapters": outline.get("target_chapters", 0),
                "chapters_count": len(outline.get("chapters", [])),
            },
        }

        logger.info(
            "Novel Orchestrator finished: workflow_id=%s, status=%s, chapters=%d/%d, words=%d, elapsed=%.1fs",
            workflow_id,
            final_result["status"],
            chapter_result.get("completed", 0),
            chapter_result.get("total_chapters", 0),
            chapter_result.get("total_words", 0),
            elapsed,
        )
        return final_result
    finally:
        # 不管成功 / 失败 / 异常：保证 ``done`` 事件被发出，让 SSE 订阅者退出
        if task_id is not None:
            try:
                if fail_status is not None:
                    _emit(
                        "done", task_id,
                        status="failed",
                        phase=fail_status[0],
                        error=fail_status[1][:300],
                    )
                else:
                    fr_status = final_result.get("status", "completed")
                    _emit(
                        "done", task_id,
                        status=fr_status,
                        workflow_id=workflow_id,
                        total_chapters=final_result.get("phases", {}).get("chapter_loop", {}).get("total_chapters", 0),
                        completed_chapters=final_result.get("phases", {}).get("chapter_loop", {}).get("completed", 0),
                        total_words=final_result.get("phases", {}).get("chapter_loop", {}).get("total_words", 0),
                        elapsed_seconds=final_result.get("elapsed_seconds", 0),
                    )
                # 关闭订阅者列表，避免泄漏
                bus.close(task_id)
            except Exception as close_exc:
                logger.debug("bus.close failed: %s", close_exc)
