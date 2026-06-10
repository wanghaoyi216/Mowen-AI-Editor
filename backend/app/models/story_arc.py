"""StoryArc — AI 生成的"故事弧线"（与 PlotLine 完全独立）。

历史说明：早期代码把 story arc 存进 ``plot_lines`` 表（plot_type='story_arc'），
导致"情节脉络"与"故事脉络"两个视图都返回同一份数据，语义混乱。
本次重构新增本表，AI 写完章节/书后会自动写入；情节脉络只走 ``plot_lines``。

字段：
  * id             — 主键
  * project_id     — 所属项目（外键 → projects.id，级联清理）
  * book_id        — 所属书（外键 → books.id，级联清理；可空 → 跨书）
  * title          — 弧线标题（如"复仇之火"）
  * arc_type       — 弧线类型（overarching / seasonal / subplot / sub_subplot）
  * description    — 一句话描述
  * start_beat     — 开端节拍（自由文本）
  * climax_beat    — 高潮节拍
  * resolution_beat — 收束节拍
  * status         — mapped / active / resolved / dropped
  * priority       — 1-5（AI 评定，越大越重要）
  * source_type    — ai_story_graph / manual
  * source_ref     — 来源任务 ID
  * created_at     — 创建时间
  * updated_at     — 更新时间
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StoryArc(Base):
    __tablename__ = "story_arcs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    book_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("books.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    arc_type: Mapped[str] = mapped_column(String(40), nullable=False, default="overarching", index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    start_beat: Mapped[str] = mapped_column(Text, nullable=False, default="")
    climax_beat: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resolution_beat: Mapped[str] = mapped_column(Text, nullable=False, default="")

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="mapped", index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="ai_story_graph")
    source_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_story_arcs_project_title", "project_id", "title"),
    )
