from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChapterPlan(Base):
    __tablename__ = "chapter_plans"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("novel_projects.id"), nullable=False, index=True)
    book_id: Mapped[int | None] = mapped_column(ForeignKey("books.id"), nullable=True, index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), nullable=False, index=True)
    plot_line_id: Mapped[int | None] = mapped_column(ForeignKey("plot_lines.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    design_brief: Mapped[str] = mapped_column(Text, nullable=False)
    beat_sheet: Mapped[str] = mapped_column(Text, nullable=False)
    asset_summary: Mapped[str] = mapped_column(Text, nullable=False)
    selected_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="planned")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
