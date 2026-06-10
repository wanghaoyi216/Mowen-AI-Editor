"""add project writing constraint fields

为 ``novel_projects`` 增加创作超参数：language / min_words_per_chapter /
max_words_per_chapter / target_chapters。这些字段会被真正注入到 LLM 创作
prompt，并用于章节字数强制校验。

Revision ID: 20260607_0001_constraints
Revises: 20260604_0002_books_scope
Create Date: 2026-06-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260607_0001_constraints"
down_revision: Union[str, Sequence[str], None] = "20260604_0002_books_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if table_name not in inspector.get_table_names():
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _column_exists(inspector, "novel_projects", "language"):
        op.add_column(
            "novel_projects",
            sa.Column("language", sa.String(length=20), nullable=False, server_default="zh-CN"),
        )
    if not _column_exists(inspector, "novel_projects", "min_words_per_chapter"):
        op.add_column(
            "novel_projects",
            sa.Column("min_words_per_chapter", sa.Integer(), nullable=False, server_default="2000"),
        )
    if not _column_exists(inspector, "novel_projects", "max_words_per_chapter"):
        op.add_column(
            "novel_projects",
            sa.Column("max_words_per_chapter", sa.Integer(), nullable=False, server_default="4000"),
        )
    if not _column_exists(inspector, "novel_projects", "target_chapters"):
        op.add_column(
            "novel_projects",
            sa.Column("target_chapters", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for column in ("target_chapters", "max_words_per_chapter", "min_words_per_chapter", "language"):
        if _column_exists(inspector, "novel_projects", column):
            op.drop_column("novel_projects", column)
