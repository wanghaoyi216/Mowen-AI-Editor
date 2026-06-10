from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StoryEvent(Base):
    __tablename__ = "story_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("novel_projects.id"), nullable=False, index=True)
    book_id: Mapped[int | None] = mapped_column(ForeignKey("books.id"), nullable=True, index=True)
    plot_line_id: Mapped[int | None] = mapped_column(ForeignKey("plot_lines.id"), nullable=True, index=True)
    chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapters.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, default="scene")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="planned")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
