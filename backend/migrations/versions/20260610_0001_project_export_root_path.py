"""为 novel_projects 增加 export_root_path

用户可在创建项目时指定一个绝对路径作为后续"按项目→任务→章节→小节→每小节.md"
层级结构导出的根目录。留空时由后端默认 EXPORT_ROOT 接管。

Revision ID: 20260610_0001_export_root
Revises: 20260609_0001_users
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260610_0001_export_root"
down_revision: Union[str, Sequence[str], None] = "20260609_0001_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if table_name not in inspector.get_table_names():
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _column_exists(inspector, "novel_projects", "export_root_path"):
        op.add_column(
            "novel_projects",
            sa.Column("export_root_path", sa.String(length=500), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _column_exists(inspector, "novel_projects", "export_root_path"):
        op.drop_column("novel_projects", "export_root_path")
