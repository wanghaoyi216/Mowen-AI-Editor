"""章节小结 (Chapter Scenes) API —— 章节下的场景/小结 CRUD。

数据模型复用 ``plot_lines`` 表：每条 plot_line 是一段场景小结。
  * title     → 场景标题（如"高潮对决"）
  * summary   → 场景摘要
  * goal      → 场景目标（角色目标）
  * conflict  → 场景冲突
  * plot_type → 固定为 "chapter_scene"
  * priority  → 场景序号（数字越小越靠前）
  * status    → planned / in_progress / completed

关联：plot_line.project_id = 章节所属项目；额外在 plot_line.summary
前缀中存 ``[chapter:{chapter_id}]`` 标识属于哪一章（轻量级关联，
避免引入新表）。

端点：
  GET  /projects/{project_id}/chapters/{chapter_id}/scenes
  POST /projects/{project_id}/chapters/{chapter_id}/scenes
  PUT  /projects/{project_id}/chapters/{chapter_id}/scenes/{scene_id}
  DELETE /projects/{project_id}/chapters/{chapter_id}/scenes/{scene_id}
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.models.chapter import Chapter
from app.models.plot_line import PlotLine
from app.schemas.common import ApiResponse
from app.schemas.plot_line import PlotLineRead


router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ChapterSceneRead(BaseModel):
    id: int
    scene_no: int
    title: str
    summary: str | None = None
    goal: str | None = None
    conflict: str | None = None
    characters_present: list[str] = Field(default_factory=list)
    emotional_tone: str | None = None
    word_count: int | None = None
    pov: str | None = None
    status: str = "planned"
    created_at: str | None = None
    updated_at: str | None = None


class ChapterSceneCreate(BaseModel):
    scene_no: int
    title: str
    summary: str | None = None
    goal: str | None = None
    conflict: str | None = None
    characters_present: list[str] = Field(default_factory=list)
    emotional_tone: str | None = None
    status: str = "planned"


class ChapterSceneUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    goal: str | None = None
    conflict: str | None = None
    characters_present: list[str] | None = None
    emotional_tone: str | None = None
    status: str | None = None


class ChapterSceneListCreate(BaseModel):
    """批量创建/替换某个章节的全部 scene。"""
    scenes: list[ChapterSceneCreate]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_CHAPTER_TAG = "chapter_scene_for:"


def _encode_chapter_tag(chapter_id: int) -> str:
    return f"{_CHAPTER_TAG}{chapter_id}"


def _extract_chapter_id(plot: PlotLine) -> int | None:
    """从 plot_line.goal 中解析出 chapter_id（轻量级反向关联）。"""
    if not plot.goal:
        return None
    match = re.search(rf"{_CHAPTER_TAG}(\d+)", plot.goal)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _inject_chapter_id(goal: str | None, chapter_id: int) -> str:
    """把 chapter_id 注入到 goal 字段。"""
    if not goal:
        return f"{_CHAPTER_TAG}{chapter_id}"
    # 移除已有 tag
    cleaned = re.sub(rf"{_CHAPTER_TAG}\d+\s*", "", goal).strip()
    return f"{_CHAPTER_TAG}{chapter_id} {cleaned}".strip()


def _parse_characters(stake_field: str | None) -> list[str]:
    """从 stakes 字段中解析角色列表（用「、」或「,」分隔）。"""
    if not stake_field:
        return []
    if "[" in stake_field and "]" in stake_field:
        match = re.search(r"\[(.*?)\]", stake_field)
        if match:
            content = match.group(1)
            return [s.strip() for s in re.split(r"[,，、;；\s]+", content) if s.strip()]
    return [s.strip() for s in re.split(r"[,，、;；\s]+", stake_field) if s.strip()]


def _parse_goal_meta(goal: str | None) -> dict[str, Any]:
    """从 plot_line.goal 文本中抽取 POV/字数/情绪 等结构化字段。
    文本格式示例：``chapter_scene_for:1\n\nPOV: 林雾\n字数: 580\n情绪: 压抑、紧张``
    """
    if not goal:
        return {"pov": None, "word_count": None, "mood": None, "clean_goal": None}
    out: dict[str, Any] = {"pov": None, "word_count": None, "mood": None, "clean_goal": None}
    pov_match = re.search(r"POV\s*[:：]\s*([^\n]+)", goal)
    if pov_match:
        out["pov"] = pov_match.group(1).strip()
    wc_match = re.search(r"字数\s*[:：]\s*(\d+)", goal)
    if wc_match:
        try:
            out["word_count"] = int(wc_match.group(1))
        except ValueError:
            pass
    mood_match = re.search(r"情绪\s*[:：]\s*([^\n]+)", goal)
    if mood_match:
        out["mood"] = mood_match.group(1).strip()
    # clean_goal = 移除 chapter_scene_for 标签后的剩余文本
    cleaned = re.sub(rf"{_CHAPTER_TAG}\d+\s*", "", goal)
    cleaned = re.sub(r"\n*POV\s*[:：][^\n]+\n?", "", cleaned)
    cleaned = re.sub(r"\n*字数\s*[:：][^\n]+\n?", "", cleaned)
    cleaned = re.sub(r"\n*情绪\s*[:：][^\n]+\n?", "", cleaned)
    cleaned = cleaned.strip("\n ").strip()
    out["clean_goal"] = cleaned or None
    return out


def _to_scene_read(plot: PlotLine, scene_no: int) -> ChapterSceneRead:
    meta = _parse_goal_meta(plot.goal)
    return ChapterSceneRead(
        id=plot.id,
        scene_no=scene_no,
        title=plot.title,
        summary=plot.summary,
        goal=meta["clean_goal"],
        conflict=plot.conflict,
        characters_present=_parse_characters(plot.stakes),
        emotional_tone=meta["mood"],
        status=plot.status,
        word_count=meta["word_count"],
        pov=meta["pov"],
        created_at=plot.created_at.isoformat() if plot.created_at else None,
        updated_at=plot.updated_at.isoformat() if plot.updated_at else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get(
    "/{project_id}/chapters/{chapter_id:int}/scenes",
    response_model=ApiResponse,
)
def list_chapter_scenes(
    project_id: int,
    chapter_id: int,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    chapter = (
        db.query(Chapter)
        .filter(Chapter.id == chapter_id, Chapter.project_id == project_id)
        .first()
    )
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

    # 通过 goal 字段中的 chapter_id 标签过滤
    all_plots = list(
        db.query(PlotLine)
        .filter(PlotLine.project_id == project_id, PlotLine.plot_type == "chapter_scene")
        .order_by(PlotLine.priority.asc())
        .all()
    )
    matched = [p for p in all_plots if _extract_chapter_id(p) == chapter_id]
    matched.sort(key=lambda p: (p.priority or 0, p.id or 0))
    scenes = [_to_scene_read(p, idx + 1) for idx, p in enumerate(matched)]
    return ApiResponse(
        message="chapter scenes listed",
        data={"scenes": [s.model_dump() for s in scenes], "total": len(scenes)},
    )


@router.post(
    "/{project_id}/chapters/{chapter_id:int}/scenes",
    response_model=ApiResponse,
)
def replace_chapter_scenes(
    project_id: int,
    chapter_id: int,
    payload: ChapterSceneListCreate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    """批量替换某个章节的全部 scene（先删后插）。"""
    chapter = (
        db.query(Chapter)
        .filter(Chapter.id == chapter_id, Chapter.project_id == project_id)
        .first()
    )
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

    # 删除该章节已有 scene
    existing = list(
        db.query(PlotLine)
        .filter(
            PlotLine.project_id == project_id,
            PlotLine.plot_type == "chapter_scene",
        )
        .all()
    )
    for p in existing:
        if _extract_chapter_id(p) == chapter_id:
            db.delete(p)
    db.flush()

    created: list[PlotLine] = []
    for scene in payload.scenes:
        plot = PlotLine(
            project_id=project_id,
            title=scene.title,
            plot_type="chapter_scene",
            summary=scene.summary,
            goal=_inject_chapter_id(scene.goal, chapter_id),
            conflict=scene.conflict,
            stakes=str(scene.characters_present) if scene.characters_present else None,
            status=scene.status or "planned",
            priority=scene.scene_no,
        )
        db.add(plot)
        created.append(plot)
    db.commit()
    for p in created:
        db.refresh(p)
    scenes = [_to_scene_read(p, idx + 1) for idx, p in enumerate(created)]
    return ApiResponse(
        message="chapter scenes replaced",
        data={"scenes": [s.model_dump() for s in scenes], "total": len(scenes)},
    )


@router.put(
    "/{project_id}/chapters/{chapter_id:int}/scenes/{scene_id:int}",
    response_model=ApiResponse,
)
def update_chapter_scene(
    project_id: int,
    chapter_id: int,
    scene_id: int,
    payload: ChapterSceneUpdate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    plot = (
        db.query(PlotLine)
        .filter(PlotLine.id == scene_id, PlotLine.project_id == project_id)
        .first()
    )
    if plot is None or _extract_chapter_id(plot) != chapter_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")
    if payload.title is not None:
        plot.title = payload.title
    if payload.summary is not None:
        plot.summary = payload.summary
    if payload.goal is not None:
        plot.goal = _inject_chapter_id(payload.goal, chapter_id)
    if payload.conflict is not None:
        plot.conflict = payload.conflict
    if payload.characters_present is not None:
        plot.stakes = str(payload.characters_present)
    if payload.status is not None:
        plot.status = payload.status
    db.commit()
    db.refresh(plot)
    return ApiResponse(
        message="chapter scene updated",
        data={"scene": _to_scene_read(plot, plot.priority or 1).model_dump()},
    )


@router.delete(
    "/{project_id}/chapters/{chapter_id:int}/scenes/{scene_id:int}",
    response_model=ApiResponse,
)
def delete_chapter_scene(
    project_id: int,
    chapter_id: int,
    scene_id: int,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    plot = (
        db.query(PlotLine)
        .filter(PlotLine.id == scene_id, PlotLine.project_id == project_id)
        .first()
    )
    if plot is None or _extract_chapter_id(plot) != chapter_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")
    db.delete(plot)
    db.commit()
    return ApiResponse(message="chapter scene deleted", data={"deleted_id": scene_id})
