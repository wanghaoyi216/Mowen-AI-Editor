"""为 story_graph 新增 story_arcs / story_themes 两张独立表

背景：
    之前 AI 在生成 story_graph_generation 时，把"故事弧线"写到 ``plot_lines``
    （plot_type='story_arc'）表，把"主题"写到 ``worldbook_entries``
    （category='theme'）表。这让"情节脉络 / 世界观"视图串台，污染了用户
    手动维护的资产。

    本次迁移把 AI 自动生成的"故事弧线 / 故事主题"切到独立的两张表，并保留
    原字段。历史 plot_type='story_arc' / category='theme' 数据保留不动
    （不再被任何视图读取），如果需要可手工迁移。

Revision ID: 20260610_0002_story_arcs_themes
Revises: 20260610_0001_export_root
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260610_0002_story_arcs_themes"
down_revision: Union[str, Sequence[str], None] = "20260610_0001_export_root"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # story_arcs —— AI 自动生成的故事弧线
    if not _table_exists(inspector, "story_arcs"):
        op.create_table(
            "story_arcs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("book_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("arc_type", sa.String(length=40), nullable=False, server_default="overarching"),
            # TEXT 列在 MySQL 上**不能**带 server_default，否则 1101 报错；
            # ORM 侧 default="" 会在 INSERT 前由 SQLAlchemy 自动补空串，保证 NOT NULL。
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("start_beat", sa.Text(), nullable=False),
            sa.Column("climax_beat", sa.Text(), nullable=False),
            sa.Column("resolution_beat", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="mapped"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("source_type", sa.String(length=40), nullable=False, server_default="ai_story_graph"),
            sa.Column("source_ref", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )

    # story_arcs 索引
    for tbl, idx, cols in [
        ("story_arcs", "ix_story_arcs_project_id", ["project_id"]),
        ("story_arcs", "ix_story_arcs_book_id", ["book_id"]),
        ("story_arcs", "ix_story_arcs_arc_type", ["arc_type"]),
        ("story_arcs", "ix_story_arcs_status", ["status"]),
        ("story_arcs", "ix_story_arcs_project_title", ["project_id", "title"]),
    ]:
        if _table_exists(inspector, tbl) and not _index_exists(inspector, tbl, idx):
            op.create_index(idx, tbl, cols)

    # story_themes —— AI 自动生成的故事主题
    if not _table_exists(inspector, "story_themes"):
        op.create_table(
            "story_themes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("book_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("represented_by", sa.Text(), nullable=False),  # JSON str
            sa.Column("arc_connection", sa.String(length=200), nullable=False, server_default=""),
            sa.Column("source_type", sa.String(length=40), nullable=False, server_default="ai_story_graph"),
            sa.Column("source_ref", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )

    for tbl, idx, cols in [
        ("story_themes", "ix_story_themes_project_id", ["project_id"]),
        ("story_themes", "ix_story_themes_book_id", ["book_id"]),
        ("story_themes", "ix_story_themes_project_name", ["project_id", "name"]),
    ]:
        if _table_exists(inspector, tbl) and not _index_exists(inspector, tbl, idx):
            op.create_index(idx, tbl, cols)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "story_themes"):
        op.drop_table("story_themes")
    if _table_exists(inspector, "story_arcs"):
        op.drop_table("story_arcs")
