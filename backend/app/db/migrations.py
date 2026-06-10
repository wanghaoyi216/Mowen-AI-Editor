"""启动期数据库迁移。

不引入 alembic（项目早期开发阶段不必要），改在 FastAPI ``on_startup`` 钩子里
按顺序执行一组**幂等**的 schema 调整。

设计原则：
  * 每次启动只跑一次；
  * 每次操作都先检查（information_schema / SHOW INDEX）再决定是否动手；
  * 失败仅记 warning，不阻断服务启动（开发友好）；
  * 主要面向 MySQL / MariaDB（生产），但尽量兼容 SQLite（开发）。

主要迁移：
  1. ``novel_projects.owner_id INT NOT NULL``：多用户隔离核心列。
     老数据 ``owner_id IS NULL`` → 回填为 ``1``（admin 用户的 id）。
  2. ``novel_projects.user_id INT NULL``：历史字段，与 ``owner_id`` 同步。
  3. ``users.email`` 唯一索引：防止多账号同邮箱。
  4. ``novel_projects(owner_id)``、``chapters(project_id)``、``books(project_id)`` 等
     已有索引由 ``create_all`` 创建；这里只补 ``novel_projects(user_id)``。

⚠ 注意：若以后引入 alembic，应把这里的逻辑迁到对应版本号。
"""

from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.db.base import engine

logger = logging.getLogger(__name__)


# ── 通用工具 ──────────────────────────────────────────────────────────────
def _column_exists(conn, table: str, column: str, dialect: str) -> bool:
    """检查表上某列是否存在。兼容 MySQL 与 SQLite。"""
    if dialect == "mysql":
        row = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).first()
    else:
        # SQLite：PRAGMA table_info(<table>) 返回 cid, name, type, ...
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return any(r[1] == column for r in rows)
    return row is not None


def _index_exists(conn, index_name: str, table: str, dialect: str) -> bool:
    """检查索引是否存在。"""
    if dialect == "mysql":
        row = conn.execute(
            text(
                "SELECT 1 FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = :t AND index_name = :i"
            ),
            {"t": table, "i": index_name},
        ).first()
        return row is not None
    # SQLite
    rows = conn.execute(text(f"PRAGMA index_list({table})")).fetchall()
    return any(r[1] == index_name for r in rows)


def _safe_add_column(conn, dialect: str, table: str, column: str, ddl: str) -> None:
    if _column_exists(conn, table, column, dialect):
        logger.debug("[migration] %s.%s 已存在，跳过", table, column)
        return
    logger.info("[migration] 添加列 %s.%s (%s)", table, column, ddl)
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def _safe_create_index(conn, dialect: str, table: str, index_name: str, cols: Iterable[str]) -> None:
    if _index_exists(conn, index_name, table, dialect):
        logger.debug("[migration] 索引 %s 已存在，跳过", index_name)
        return
    cols_sql = ", ".join(cols)
    logger.info("[migration] 建索引 %s (%s.%s)", index_name, table, cols_sql)
    conn.execute(text(f"CREATE INDEX {index_name} ON {table} ({cols_sql})"))


# ── 主入口 ────────────────────────────────────────────────────────────────
def run_startup_migrations() -> None:
    """启动时跑一遍幂等迁移。失败仅 warning，不抛。"""
    # 只在 MySQL / MariaDB / SQLite 上做。其它 DB 直接跳过。
    url = str(engine.url)
    if url.startswith("mysql"):
        dialect = "mysql"
    elif url.startswith("sqlite"):
        dialect = "sqlite"
    else:
        logger.info("[migration] 未识别的方言 %s，跳过启动迁移", url)
        return

    with engine.begin() as conn:
        # 1. novel_projects.owner_id
        if dialect == "mysql":
            _safe_add_column(
                conn, dialect, "novel_projects", "owner_id",
                "INT NOT NULL DEFAULT 1",
            )
        else:
            # SQLite 允许 NULL 暂存，update 完再 NOT NULL
            _safe_add_column(conn, dialect, "novel_projects", "owner_id", "INTEGER")
            # 把 NULL 的回填 1
            conn.execute(text("UPDATE novel_projects SET owner_id = 1 WHERE owner_id IS NULL"))
            # SQLite 不能直接 ALTER NOT NULL，但 INTEGER NOT NULL 在 ORM 层是必填；
            # create_all 已经加了 NOT NULL，OK。

        # 同步 user_id（兼容旧调用点）
        _safe_add_column(conn, dialect, "novel_projects", "user_id", "INTEGER")
        conn.execute(text("UPDATE novel_projects SET user_id = owner_id WHERE user_id IS NULL OR user_id <> owner_id"))

        # 索引：owner_id 和 user_id 都要
        _safe_create_index(conn, dialect, "novel_projects", "ix_novel_projects_owner_id", ["owner_id"])
        _safe_create_index(conn, dialect, "novel_projects", "ix_novel_projects_user_id", ["user_id"])

        # 2. users.email 唯一索引
        # 先看列存不存在（如果是早期迁移没有 email 列则跳过）
        if _column_exists(conn, "users", "email", dialect):
            try:
                _safe_create_index(conn, dialect, "users", "uq_users_email", ["email"])
            except SQLAlchemyError as e:
                # 已有重复 email 导致建索引失败 → 记 warning，不阻断启动
                logger.warning("[migration] users.email 唯一索引创建失败（可能存在重复值）: %s", e)

        # 3. chapters / books / characters 的 project_id 索引
        # create_all 会建；这里只是兜底
        for tbl in ("chapters", "books", "characters", "worldbook_entries", "plot_lines",
                    "story_events", "story_arcs", "story_themes",
                    "confirmation_requests"):
            if _column_exists(conn, tbl, "project_id", dialect):
                _safe_create_index(conn, dialect, tbl, f"ix_{tbl}_project_id", ["project_id"])

    logger.info("[migration] 启动迁移完成 (dialect=%s)", dialect)


if __name__ == "__main__":  # 调试用
    logging.basicConfig(level=logging.INFO)
    run_startup_migrations()
