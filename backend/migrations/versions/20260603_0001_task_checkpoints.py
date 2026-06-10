"""add task_checkpoints table

Revision ID: 20260603_0001_task_checkpoints
Revises: 20260602_0004_task_logs_step_no
Create Date: 2026-06-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260603_0001_task_checkpoints"
down_revision: Union[str, None] = "20260602_0004_task_logs_step_no"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("ai_tasks.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("novel_projects.id"), nullable=False),
        sa.Column("checkpoint_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_task_checkpoints_id", "task_checkpoints", ["id"])
    op.create_index("ix_task_checkpoints_task_id", "task_checkpoints", ["task_id"])
    op.create_index("ix_task_checkpoints_project_id", "task_checkpoints", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_task_checkpoints_project_id", table_name="task_checkpoints")
    op.drop_index("ix_task_checkpoints_task_id", table_name="task_checkpoints")
    op.drop_index("ix_task_checkpoints_id", table_name="task_checkpoints")
    op.drop_table("task_checkpoints")
