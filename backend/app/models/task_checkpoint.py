from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TaskCheckpoint(Base):
    __tablename__ = "task_checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("ai_tasks.id"), nullable=False, index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("novel_projects.id"), nullable=False, index=True
    )
    checkpoint_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
