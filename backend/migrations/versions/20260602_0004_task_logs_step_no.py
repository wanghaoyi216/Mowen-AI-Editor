"""add step_no to task_logs

Revision ID: 20260602_0004_task_logs_step_no
Revises: 20260601_0003_workflow_execution_id
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260602_0004_task_logs_step_no"
down_revision: Union[str, None] = "20260601_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("task_logs", sa.Column("step_no", sa.Integer(), nullable=True))
    op.create_index("ix_task_logs_step_no", "task_logs", ["step_no"])


def downgrade() -> None:
    op.drop_index("ix_task_logs_step_no", table_name="task_logs")
    op.drop_column("task_logs", "step_no")
