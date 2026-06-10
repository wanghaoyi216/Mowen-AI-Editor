"""清空业务数据，保留数据库表结构。

支持 MySQL / SQLite / PostgreSQL。默认清空所有运行数据（含项目和书籍），
用于正式部署前移除本地测试数据。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import settings  # noqa: E402
from app.db.base import SessionLocal  # noqa: E402


BUSINESS_TABLES = [
    "confirmation_requests",
    "content_embeddings",
    "character_event_participations",
    "character_relationships",
    "chapter_versions",
    "chapter_plans",
    "story_events",
    "plot_lines",
    "characters",
    "worldbook_entries",
    "trend_explorations",
    "task_logs",
    "task_steps",
    "ai_tasks",
    "chapters",
    "books",
    "novel_projects",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="清空数据库中的运行数据。")
    parser.add_argument("--force", action="store_true", help="跳过交互确认，直接执行清理。")
    return parser.parse_args()


def confirm_or_exit(force: bool) -> None:
    print("警告：即将清空数据库中的运行数据。")
    print("保留：所有表结构、索引和迁移记录。")
    print("清理表：")
    for table_name in BUSINESS_TABLES:
        print(f"  - {table_name}")

    if force:
        print("已使用 --force，跳过交互确认。")
        return

    answer = input("请输入 CLEAN 确认执行清理：").strip()
    if answer != "CLEAN":
        print("未确认，已取消清理。")
        raise SystemExit(0)


def _quote_identifier(dialect_name: str, table_name: str) -> str:
    quote = "`" if dialect_name == "mysql" else '"'
    return f"{quote}{table_name}{quote}"


def _existing_tables(session, dialect_name: str) -> list[str]:
    rows = session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE()")).all() if dialect_name == "mysql" else None
    if rows is not None:
        existing = {row[0] for row in rows}
        return [table_name for table_name in BUSINESS_TABLES if table_name in existing]

    bind = session.get_bind()
    if dialect_name == "sqlite":
        rows = session.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'")).all()
        existing = {row[0] for row in rows}
        return [table_name for table_name in BUSINESS_TABLES if table_name in existing]

    rows = session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()")).all()
    existing = {row[0] for row in rows}
    return [table_name for table_name in BUSINESS_TABLES if table_name in existing]


def count_rows(session, table_names: list[str], dialect_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table_name in table_names:
        quoted = _quote_identifier(dialect_name, table_name)
        counts[table_name] = session.execute(
            text(f"SELECT COUNT(*) FROM {quoted}")
        ).scalar_one()
    return counts


def clean_database() -> dict[str, int]:
    session = SessionLocal()
    try:
        dialect_name = session.get_bind().dialect.name
        table_names = _existing_tables(session, dialect_name)
        before_counts = count_rows(session, table_names, dialect_name)

        if dialect_name == "mysql":
            session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            for table_name in table_names:
                session.execute(text(f"TRUNCATE TABLE {_quote_identifier(dialect_name, table_name)}"))
            session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        elif dialect_name == "sqlite":
            session.execute(text("PRAGMA foreign_keys = OFF"))
            for table_name in table_names:
                session.execute(text(f"DELETE FROM {_quote_identifier(dialect_name, table_name)}"))
            session.execute(text("PRAGMA foreign_keys = ON"))
        else:
            quoted_tables = ", ".join(_quote_identifier(dialect_name, table_name) for table_name in table_names)
            if quoted_tables:
                session.execute(text(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE"))
        session.commit()
        return before_counts
    except Exception as exc:
        session.rollback()
        print(f"数据库清理失败：{exc}", file=sys.stderr)
        raise
    finally:
        session.close()


def main() -> int:
    args = parse_args()
    confirm_or_exit(args.force)

    print(f"数据库连接：{settings.database_url}")
    try:
        cleaned_counts = clean_database()
    except Exception:
        return 1

    print("数据库运行数据清理完成：")
    for table_name, row_count in cleaned_counts.items():
        print(f"  - {table_name}: 清理 {row_count} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
