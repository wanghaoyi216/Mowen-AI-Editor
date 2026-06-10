from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TrendExploration(Base):
    __tablename__ = "trend_explorations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("novel_projects.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_scope: Mapped[str | None] = mapped_column(String(100), nullable=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_topics: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_directions: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
