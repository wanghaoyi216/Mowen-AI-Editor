"""故事脉络 (Story Arc) API —— Tab7 真实数据源。

从 ``chapters`` / ``chapter_plans`` / ``plot_lines`` / ``characters`` 联合查询，
生成可视化所需的节点与边数据。

节点类型：
  * chapter        — 章节节点（每个 chapter 一节点）
  * climax         — 高潮（章节包含「高潮 / 决战 / 巅峰」等关键词或 conflict 关键词标记）
  * turning_point  — 转折点（章节包含「转折 / 突变 / 觉醒」等关键词）
  * conflict       — 冲突（章节 conflict 字段非空）
  * ending         — 结局（最后一个章节或 status=completed 收束；最高 chapter_no 兜底）
  * scene          — 场景（chapter_scene plot_line 节点）
  * plot_line      — 剧情线（主剧情线节点，独立类型）

边关系：
  * sequel_to     — 相邻章节 A→B
  * leads_to     — 章节 A 的 key_events 引导到章节 B
  * conflicts_with — 两个 chapter 共享同一 conflict 关键词（关键词交集）
  * resolves     — 章节 A conflict 化解（status=completed 且 conflict 为空 / summary 含化解关键词）
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.routes._guards import get_owned_project
from app.models.book import Book
from app.models.chapter import Chapter
from app.models.chapter_plan import ChapterPlan
from app.models.plot_line import PlotLine
from app.models.project import NovelProject
from app.schemas.common import ApiResponse


router = APIRouter()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 分类启发式（中文关键词）
# ---------------------------------------------------------------------------
_CLIMAX_KEYWORDS = ("高潮", "决战", "巅峰", "顶峰", "终极", "最终战", "climax", "决战篇")
_TURNING_KEYWORDS = ("转折", "突变", "觉醒", "揭秘", "反败为胜", "turning", "逆转")
_CONFLICT_KEYWORDS = ("冲突", "矛盾", "危机", "对抗", "冲突点", "conflict", "矛盾点")

# conflict 字段关键词分隔符（半角逗号 / 全角逗号 / 全角句号 / 半角分号 / 全角分号 / 换行 / 顿号）
_CONFLICT_SPLIT_RE = re.compile(r"[,，。;；\n、]")
# scene 标题分隔符（中点 / 半角竖线 / 全角竖线 / 斜杠 / 全角斜杠 / 冒号 / 全角冒号）
_SCENE_TITLE_SPLIT_RE = re.compile(r"[·|｜/／:：]")
# resolves 边判断时 summary 中需含的"化解"关键词
_RESOLVE_KEYWORDS = ("解决", "化解", "结束", "平息", "破除", "释怀", "和解")


def _split_conflict(s: str | None) -> set[str]:
    """将 conflict 字段按常见标点拆成关键词集合。空字符串/None 返回空集合。"""
    if not s:
        return set()
    return {k.strip() for k in _CONFLICT_SPLIT_RE.split(s) if k.strip()}


def _classify_chapter_type(chapter: Chapter) -> str:
    """根据章节标题 / 摘要 / conflict 字段判断节点类型。

    优先级：ending（标题含'终'） > climax > turning_point > conflict > chapter
    兜底 ending 在 read_story_arc 中按"最高 chapter_no + 已写/已完成"再判一次。
    """
    title = (chapter.title or "").lower()
    summary = (chapter.summary or "").lower()
    objective = (chapter.objective or "").lower()
    conflict = (chapter.conflict or "").lower()
    text = f"{title} {summary} {objective} {conflict}"

    if chapter.status == "completed" and chapter.chapter_no and not conflict:
        if any(kw in title for kw in ("终", "结", "大结局", "尾声", "结局", "end", "finale")):
            return "ending"
    for kw in _CLIMAX_KEYWORDS:
        if kw in text:
            return "climax"
    for kw in _TURNING_KEYWORDS:
        if kw in text:
            return "turning_point"
    for kw in _CONFLICT_KEYWORDS:
        if kw in text or conflict:
            return "conflict"
    return "chapter"


def _extract_emotional_arc(chapter: Chapter) -> str:
    """提取章节情绪（情绪曲线标签）。"""
    title = chapter.title or ""
    if any(kw in title for kw in ("泪", "悲", "虐", "痛")):
        return "悲怆"
    if any(kw in title for kw in ("战", "决", "胜", "高潮")):
        return "激昂"
    if any(kw in title for kw in ("平", "日常", "晨", "夜")):
        return "舒缓"
    return "起伏"


def _build_chapter_node(chapter: Chapter) -> dict[str, Any]:
    node_type = _classify_chapter_type(chapter)
    emotional_arc = _extract_emotional_arc(chapter)
    label = f"第{chapter.chapter_no}章 {chapter.title or '未命名'}"[:32]
    return {
        "id": f"chapter-{chapter.id}",
        "type": node_type,
        "label": label,
        "chapterNo": chapter.chapter_no,
        "theme": chapter.objective or chapter.summary or "",
        "emotionalArc": emotional_arc,
        "status": chapter.status or "draft",
        "wordCount": chapter.word_count or 0,
    }


def _build_plot_line_node(plot: PlotLine) -> dict[str, Any]:
    return {
        "id": f"plot-{plot.id}",
        "type": "plot_line",
        "label": f"剧情线: {(plot.title or '未命名')[:24]}",
        "chapterNo": None,
        "theme": plot.summary or plot.goal or "",
        "emotionalArc": "",
        "wordCount": 0,
        "plotLineId": plot.id,
        "plotType": plot.plot_type,
    }


def _build_edges(
    chapters: list[Chapter],
) -> list[dict[str, Any]]:
    """按章节顺序构建 sequel_to 边，并按关键词交集构建 conflicts_with 边。"""
    edges: list[dict[str, Any]] = []
    sorted_chapters = sorted(
        chapters,
        key=lambda c: (c.chapter_no is None, c.chapter_no or 0),
    )
    for i, ch in enumerate(sorted_chapters):
        if i + 1 < len(sorted_chapters):
            nxt = sorted_chapters[i + 1]
            edges.append({
                "source": f"chapter-{ch.id}",
                "target": f"chapter-{nxt.id}",
                "relation": "sequel_to",
                "weight": 1.0,
            })
    # conflicts_with：任意两章节 conflict 关键词集合有交集
    for i in range(len(sorted_chapters)):
        for j in range(i + 1, len(sorted_chapters)):
            a, b = sorted_chapters[i], sorted_chapters[j]
            a_kw = _split_conflict(a.conflict)
            b_kw = _split_conflict(b.conflict)
            if a_kw and b_kw:
                inter = a_kw & b_kw
                uni = a_kw | b_kw
                if inter and uni:
                    weight = round(len(inter) / len(uni), 3)
                    edges.append({
                        "source": f"chapter-{a.id}",
                        "target": f"chapter-{b.id}",
                        "relation": "conflicts_with",
                        "weight": weight,
                        "label": f"冲突·{','.join(sorted(inter))[:20]}",
                    })
    return edges


def _build_resolves_edges(
    chapters: list[Chapter],
    existing: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """resolves 边：A.conflict 关键词 K + B.summary 含 K（或含化解关键词）+ B.conflict 不含 K。"""
    edges: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for i in range(len(chapters)):
        for j in range(i + 1, len(chapters)):
            ca, cb = chapters[i], chapters[j]
            if not ca.conflict or not ca.id or not cb.id:
                continue
            ca_kw = _split_conflict(ca.conflict)
            cb_kw = _split_conflict(cb.conflict)
            cb_summary = cb.summary or ""
            for k in ca_kw:
                if k in cb_kw:
                    continue  # 冲突还在，没化解
                if k in cb_summary or any(rk in cb_summary for rk in _RESOLVE_KEYWORDS):
                    key = (ca.id, cb.id)
                    if key in seen:
                        continue
                    seen.add(key)
                    edges.append({
                        "source": f"chapter-{ca.id}",
                        "target": f"chapter-{cb.id}",
                        "relation": "resolves",
                        "weight": 0.7,
                        "label": f"化解·{k}",
                    })
    return edges


@router.get("/{project_id}/story-arc", response_model=ApiResponse)
def read_story_arc(
    project_id: int,
    book_id: int | None = None,
    plot_limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> ApiResponse:
    """读取项目的故事脉络数据。

    返回结构：
    {
      "nodes": [
        { "id": "chapter-1", "type": "chapter", "label": "第一章 ...", "chapterNo": 1, "theme": "...", "emotionalArc": "起伏", "wordCount": 0, "status": "draft" },
        { "id": "scene-166", "type": "scene", "label": "场景1: ...", "chapterNo": 1, "emotionalArc": "", "wordCount": 0 },
        { "id": "plot-3", "type": "plot_line", "label": "剧情线: ...", "chapterNo": null, "emotionalArc": "", "wordCount": 0 },
        ...
      ],
      "edges": [
        { "source": "chapter-1", "target": "chapter-2", "relation": "sequel_to", "weight": 1.0 },
        { "source": "chapter-1", "target": "scene-166", "relation": "leads_to", "weight": 0.5 },
        { "source": "chapter-1", "target": "chapter-3", "relation": "conflicts_with", "weight": 0.5, "label": "冲突·K" },
        { "source": "chapter-1", "target": "chapter-3", "relation": "resolves", "weight": 0.7, "label": "化解·K" }
      ],
      "stats": {
        "chapters": 0, "plotLines": 0, "plans": 0, "scenes": 0, "orphanScenes": 0,
        "emotionalArc": {"悲怆": 0, "激昂": 0, "舒缓": 0, "起伏": 0},
        "wordCountByChapter": [{"chapterNo": 1, "wordCount": 0}],
        "generatedAt": "2026-06-08T...Z", "version": 2
      },
      "bookId": null,
      "version": 2,
      "generatedAt": "2026-06-08T...Z"
    }
    """
    orphan_scenes = 0
    # 当 book_id 过滤后为 0 时（例如 book_id 已删除、book_id 来自不同项目、
    # 或当前 book_id 不在 books 列表里），自动回退到 project_id 级别。
    # 这样能避免因错误的 bookId 导致故事脉络一片空白。
    effective_book_id = book_id
    if book_id is not None:
        book_exists = db.query(Book).filter(
            Book.id == book_id,
            Book.project_id == project_id,
        ).first()
        if book_exists is None:
            logger.warning(
                "story-arc: book_id=%s 不属于 project_id=%s，自动忽略 book 过滤",
                book_id,
                project_id,
            )
            effective_book_id = None
    try:
        chapter_query = db.query(Chapter).filter(Chapter.project_id == project_id)
        if effective_book_id is not None:
            chapter_query = chapter_query.filter(Chapter.book_id == effective_book_id)
        # MySQL 不支持 NULLS LAST；用 (col IS NULL) ASC, col ASC 兼容
        chapters = list(
            chapter_query.order_by(
                Chapter.chapter_no.is_(None).asc(),
                Chapter.chapter_no.asc(),
            ).all()
        )
        if not chapters:
            return ApiResponse(
                success=True,
                code=200,
                message="项目下暂无章节数据，AI 完成大纲后会自动生成故事脉络",
                data={
                    "nodes": [],
                    "edges": [],
                    "stats": {
                        "chapters": 0,
                        "plotLines": 0,
                        "plans": 0,
                        "scenes": 0,
                        "orphanScenes": 0,
                        "emotionalArc": {"悲怆": 0, "激昂": 0, "舒缓": 0, "起伏": 0},
                        "wordCountByChapter": [],
                        "generatedAt": datetime.utcnow().isoformat() + "Z",
                        "version": 2,
                    },
                    "bookId": effective_book_id,
                    "version": 2,
                    "generatedAt": datetime.utcnow().isoformat() + "Z",
                },
            )

        # 节点：每个章节 + 关联 plot_line（主剧情线，过滤掉 chapter_scene）
        nodes: list[dict[str, Any]] = [_build_chapter_node(c) for c in chapters]
        plot_query = db.query(PlotLine).filter(
            PlotLine.project_id == project_id,
            PlotLine.plot_type != "chapter_scene",
        )
        if book_id is not None:
            plot_query = plot_query.filter(PlotLine.book_id == book_id)
        plot_lines = list(
            plot_query.order_by(
                PlotLine.priority.is_(None).asc(),
                PlotLine.priority.desc(),
            ).limit(plot_limit).all()
        )
        for pl in plot_lines:
            nodes.append(_build_plot_line_node(pl))

        # 章节下的 scene 节点（chapter_scene plot_lines）
        chapter_ids = {c.id for c in chapters}
        scene_query = db.query(PlotLine).filter(
            PlotLine.project_id == project_id,
            PlotLine.plot_type == "chapter_scene",
            PlotLine.chapter_id.in_(chapter_ids),
        )
        if effective_book_id is not None:
            scene_query = scene_query.filter(PlotLine.book_id == effective_book_id)
        scene_pls = list(
            scene_query.order_by(
                PlotLine.chapter_id.is_(None).asc(),
                PlotLine.chapter_id.asc(),
                PlotLine.scene_order.is_(None).asc(),
                PlotLine.scene_order.asc(),
            ).all()
        )
        scene_count = 0
        for sp in scene_pls:
            # title 形如 "第1章 · 场景1 · 晨雾中的卷宗"，按多种分隔符拆，取最后一段
            title_text = sp.title or ""
            parts = _SCENE_TITLE_SPLIT_RE.split(title_text)
            if len(parts) > 1 and parts[-1].strip():
                scene_name = parts[-1].strip()
            else:
                scene_name = title_text.strip() or f"场景{sp.scene_order or 0}"
            # chapterNo 提取（带存在性 fallback）
            scene_chapter_no = None
            if sp.chapter_id is not None:
                matched = next(
                    (c.chapter_no for c in chapters if c.id == sp.chapter_id),
                    None,
                )
                scene_chapter_no = matched
            nodes.append({
                "id": f"scene-{sp.id}",
                "type": "scene",
                "label": f"场景{sp.scene_order}: {scene_name[:20]}",
                "chapterNo": scene_chapter_no,
                "theme": sp.summary or sp.goal or "",
                "emotionalArc": "",
                "wordCount": 0,
                "plotLineId": sp.id,
                "plotType": sp.plot_type,
                "sceneOrder": sp.scene_order,
            })
            scene_count += 1

        # ending 兜底：最高 chapter_no + status in (completed, writing) → ending
        max_chapter_no = 0
        for c in chapters:
            if c.chapter_no is not None and c.chapter_no > max_chapter_no:
                max_chapter_no = c.chapter_no
        if max_chapter_no > 0:
            for n in nodes:
                if (
                    n.get("type") == "chapter"
                    and n.get("chapterNo") == max_chapter_no
                ):
                    ch = next(
                        (c for c in chapters if c.chapter_no == max_chapter_no),
                        None,
                    )
                    if ch and (ch.status in ("completed", "writing")):
                        n["type"] = "ending"
                    break  # 只处理一个候选

        # 边：sequel_to + conflicts_with
        edges = _build_edges(chapters)
        # resolves 边
        edges.extend(_build_resolves_edges(chapters))

        # scene → chapter 的 leads_to 边（孤儿检查）
        for sp in scene_pls:
            if sp.chapter_id is not None and sp.chapter_id in chapter_ids:
                edges.append({
                    "source": f"chapter-{sp.chapter_id}",
                    "target": f"scene-{sp.id}",
                    "relation": "leads_to",
                    "weight": 0.5,
                })
            else:
                orphan_scenes += 1

        # ChapterPlan：plot_line → chapter 的 leads_to 边
        plan_query = db.query(ChapterPlan).filter(ChapterPlan.project_id == project_id)
        if book_id is not None:
            plan_query = plan_query.filter(ChapterPlan.book_id == book_id)
        chapter_plans = list(plan_query.all())
        for pl in plot_lines:
            for cp in chapter_plans:
                if cp.plot_line_id == pl.id and cp.chapter_id:
                    edge = {
                        "source": f"plot-{pl.id}",
                        "target": f"chapter-{cp.chapter_id}",
                        "relation": "leads_to",
                        "weight": 0.8,
                    }
                    if edge not in edges:
                        edges.append(edge)

        # stats：情绪分布 + 字数趋势
        emotional_arc_count: dict[str, int] = {"悲怆": 0, "激昂": 0, "舒缓": 0, "起伏": 0}
        word_count_by_chapter: list[dict[str, Any]] = []
        for c in chapters:
            arc = _extract_emotional_arc(c)
            if arc in emotional_arc_count:
                emotional_arc_count[arc] += 1
            else:
                # 兜底：出现未识别情绪时单列一个 key
                emotional_arc_count[arc] = 1
            word_count_by_chapter.append({
                "chapterNo": c.chapter_no or 0,
                "wordCount": c.word_count or 0,
            })

        stats = {
            "chapters": len(chapters),
            "plotLines": len(plot_lines),
            "plans": len(chapter_plans),
            "scenes": scene_count,
            "orphanScenes": orphan_scenes,
            "emotionalArc": emotional_arc_count,
            "wordCountByChapter": word_count_by_chapter,
            "generatedAt": datetime.utcnow().isoformat() + "Z",
            "version": 2,
        }

        return ApiResponse(
            success=True,
            code=200,
            message="ok",
            data={
                "nodes": nodes,
                "edges": edges,
                "stats": stats,
                "bookId": effective_book_id,
                "version": 2,
                "generatedAt": datetime.utcnow().isoformat() + "Z",
            },
        )
    except SQLAlchemyError as e:
        logger.error(
            "story arc query failed: project_id=%s, book_id=%s, error=%s",
            project_id,
            book_id,
            e,
            exc_info=True,
        )
        return ApiResponse(
            success=False,
            code=503,
            message=f"故事脉络查询失败: {str(e)[:80]}",
            data={
                "nodes": [],
                "edges": [],
                "stats": {
                    "chapters": 0,
                    "plotLines": 0,
                    "plans": 0,
                    "scenes": 0,
                    "orphanScenes": 0,
                    "emotionalArc": {"悲怆": 0, "激昂": 0, "舒缓": 0, "起伏": 0},
                    "wordCountByChapter": [],
                    "generatedAt": datetime.utcnow().isoformat() + "Z",
                    "version": 2,
                },
                "bookId": effective_book_id,
                "version": 2,
                "generatedAt": datetime.utcnow().isoformat() + "Z",
            },
        )
