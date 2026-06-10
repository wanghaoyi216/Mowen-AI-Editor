"""StoryTheme — AI 生成的"故事主题"（与 WorldbookEntry 完全独立）。

历史说明：早期代码把 theme 存进 ``worldbook_entries`` 表（category='theme'），
导致"世界观"视图与"主题"数据混在一起。
本次重构新增本表。

字段：
  * id              — 主键
  * project_id      — 所属项目
  * book_id         — 所属书（可空）
  * name            — 主题名（如"救赎"、"命运"）
  * description     — 主题描述
  * represented_by  — JSON 字符串数组，承载主题的角色名
  * arc_connection  — 与弧线的关联描述（自由文本）
  * source_type     — ai_story_graph / manual
  * created_at      — 创建时间
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StoryTheme(Base):
    __tablename__ = "story_themes"

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

    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    represented_by: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    arc_connection: Mapped[str] = mapped_column(Text, nullable=False, default="")

    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="ai_story_graph")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_story_themes_project_name", "project_id", "name"),
    )
