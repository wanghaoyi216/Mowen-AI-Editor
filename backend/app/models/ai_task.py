from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AITask(Base):
    __tablename__ = "ai_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("novel_projects.id"), nullable=False, index=True)
    chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapters.id"), nullable=True, index=True)
    plot_line_id: Mapped[int | None] = mapped_column(nullable=True)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    module_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    input_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_execution_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str | None] = mapped_column(String(20), nullable=True, server_default="confirm")
    current_workflow_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_confirmation_point: Mapped[str | None] = mapped_column(String(50), nullable=True)
    human_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TaskStep(Base):
    __tablename__ = "task_steps"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("ai_tasks.id"), nullable=False, index=True)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(200), nullable=False)
    step_type: Mapped[str] = mapped_column(String(100), nullable=False)
    react_state: Mapped[str] = mapped_column(String(100), nullable=False)
    input_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskLog(Base):
    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("ai_tasks.id"), nullable=False, index=True)
    step_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    log_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
