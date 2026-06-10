"""add chapter versions

Revision ID: 20260531_0002
Revises: 20260531_0001
Create Date: 2026-05-31 00:00:02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260531_0002"
down_revision: Union[str, Sequence[str], None] = "20260531_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chapter_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("novel_projects.id"), nullable=False),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("operation_type", sa.String(length=100), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("consistency_report", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("selected_model", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chapter_versions_id", "chapter_versions", ["id"])
    op.create_index("ix_chapter_versions_project_id", "chapter_versions", ["project_id"])
    op.create_index("ix_chapter_versions_chapter_id", "chapter_versions", ["chapter_id"])


def downgrade() -> None:
    op.drop_index("ix_chapter_versions_chapter_id", table_name="chapter_versions")
    op.drop_index("ix_chapter_versions_project_id", table_name="chapter_versions")
    op.drop_index("ix_chapter_versions_id", table_name="chapter_versions")
    op.drop_table("chapter_versions")
