from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConfirmationRequest(Base):
    __tablename__ = "confirmation_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("ai_tasks.id"))
    workflow_id: Mapped[str] = mapped_column(String(50))
    point_id: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    human_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
