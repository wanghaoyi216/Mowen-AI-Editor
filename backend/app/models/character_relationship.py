from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CharacterRelationship(Base):
    __tablename__ = "character_relationships"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("novel_projects.id"), nullable=False, index=True)
    book_id: Mapped[int | None] = mapped_column(ForeignKey("books.id"), nullable=True, index=True)
    source_character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), nullable=False, index=True)
    target_character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    intensity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
