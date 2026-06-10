from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChapterVersion(Base):
    __tablename__ = "chapter_versions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("novel_projects.id"), nullable=False, index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_type: Mapped[str] = mapped_column(String(100), nullable=False, default="draft_generation")
    instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    consistency_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
