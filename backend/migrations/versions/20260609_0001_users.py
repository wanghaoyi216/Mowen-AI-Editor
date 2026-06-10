"""用户表 (users) —— 用户登录/注册支持

Revision ID: 20260609_0001_users
Revises: 20260607_0001_project_writing_constraints
Create Date: 2026-06-09

说明：
- 新增 users 表（id / username / email / password_hash / display_name / created_at / updated_at）
- 用户名唯一索引
- 邮箱可选，但有索引（用于找回密码等场景）
- 密码使用 bcrypt 哈希存储（不在此 migration 引入依赖，hash 字段长度 255 足够）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260609_0001_users"
down_revision: Union[str, Sequence[str], None] = "20260607_0001_constraints"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_MYSQL_TABLE_KW = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("username", sa.String(length=64), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("display_name", sa.String(length=120), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            **_MYSQL_TABLE_KW,
        )
        inspector = sa.inspect(bind)

    if not any(idx["name"] == "ix_users_username" for idx in inspector.get_indexes("users")):
        op.create_index("ix_users_username", "users", ["username"], unique=True)
    if not any(idx["name"] == "ix_users_email" for idx in inspector.get_indexes("users")):
        op.create_index("ix_users_email", "users", ["email"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" in inspector.get_table_names():
        op.drop_table("users")
