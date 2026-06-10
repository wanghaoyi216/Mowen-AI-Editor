from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("novel_projects.id"), nullable=False, index=True)
    book_id: Mapped[int | None] = mapped_column(ForeignKey("books.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    alias: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(50), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    identity: Mapped[str | None] = mapped_column(String(200), nullable=True)
    personality: Mapped[str | None] = mapped_column(Text, nullable=True)
    motivation: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    fear: Mapped[str | None] = mapped_column(Text, nullable=True)
    secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    background: Mapped[str | None] = mapped_column(Text, nullable=True)
    appearance: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    arc_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
