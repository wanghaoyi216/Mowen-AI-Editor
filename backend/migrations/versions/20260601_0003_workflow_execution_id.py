"""add workflow execution id

Revision ID: 20260601_0003
Revises: 20260531_0002
Create Date: 2026-06-01 00:00:03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260601_0003"
down_revision: Union[str, Sequence[str], None] = "20260531_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_tasks", sa.Column("workflow_execution_id", sa.String(length=120), nullable=True))
    op.create_index("ix_ai_tasks_workflow_execution_id", "ai_tasks", ["workflow_execution_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_tasks_workflow_execution_id", table_name="ai_tasks")
    op.drop_column("ai_tasks", "workflow_execution_id")
