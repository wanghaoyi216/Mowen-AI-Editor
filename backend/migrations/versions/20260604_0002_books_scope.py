"""add book-scoped schema fields

Revision ID: 20260604_0002_books_scope
Revises: 20260604_0001_mysql_initial
Create Date: 2026-06-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260604_0002_books_scope"
down_revision: Union[str, Sequence[str], None] = "20260604_0001_mysql_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_MYSQL_TABLE_KW = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _fk_exists(inspector: sa.Inspector, table_name: str, fk_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(table_name))


def _add_index_if_missing(inspector: sa.Inspector, table_name: str, index_name: str, columns: list[str]) -> None:
    if not _index_exists(inspector, table_name, index_name):
        op.create_index(index_name, table_name, columns)


def _add_fk_if_missing(
    inspector: sa.Inspector,
    table_name: str,
    fk_name: str,
    columns: list[str],
    referred_table: str,
    referred_columns: list[str],
) -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    if not _fk_exists(inspector, table_name, fk_name):
        op.create_foreign_key(fk_name, table_name, referred_table, columns, referred_columns)


def _add_book_id(inspector: sa.Inspector, table_name: str, fk_name: str, index_name: str) -> None:
    if not _column_exists(inspector, table_name, "book_id"):
        op.add_column(table_name, sa.Column("book_id", sa.Integer(), nullable=True))
    _add_index_if_missing(inspector, table_name, index_name, ["book_id"])
    _add_fk_if_missing(inspector, table_name, fk_name, ["book_id"], "books", ["id"])


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "books"):
        op.create_table(
            "books",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("novel_projects.id"), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            **_MYSQL_TABLE_KW,
        )
        inspector = sa.inspect(bind)
    _add_index_if_missing(inspector, "books", "ix_books_id", ["id"])
    _add_index_if_missing(inspector, "books", "ix_books_project_id", ["project_id"])

    for table_name, fk_name, index_name in (
        ("chapters", "fk_chapters_book", "ix_chapters_book_id"),
        ("characters", "fk_characters_book", "ix_characters_book_id"),
        ("character_relationships", "fk_character_relationships_book", "ix_character_relationships_book_id"),
        ("character_event_participations", "fk_character_event_participations_book", "ix_character_event_participations_book_id"),
        ("chapter_plans", "fk_chapter_plans_book", "ix_chapter_plans_book_id"),
        ("plot_lines", "fk_plot_lines_book", "ix_plot_lines_book_id"),
        ("story_events", "fk_story_events_book", "ix_story_events_book_id"),
        ("worldbook_entries", "fk_worldbook_entries_book", "ix_worldbook_entries_book_id"),
    ):
        inspector = sa.inspect(bind)
        _add_book_id(inspector, table_name, fk_name, index_name)

    inspector = sa.inspect(bind)
    if not _column_exists(inspector, "plot_lines", "chapter_id"):
        op.add_column("plot_lines", sa.Column("chapter_id", sa.Integer(), nullable=True))
    inspector = sa.inspect(bind)
    _add_index_if_missing(inspector, "plot_lines", "ix_plot_lines_chapter_id", ["chapter_id"])
    _add_fk_if_missing(inspector, "plot_lines", "fk_plot_lines_chapter", ["chapter_id"], "chapters", ["id"])

    inspector = sa.inspect(bind)
    if not _column_exists(inspector, "plot_lines", "scene_order"):
        op.add_column("plot_lines", sa.Column("scene_order", sa.Integer(), nullable=False, server_default="0"))

    # Backfill one default book per project and attach existing records to it.
    dialect_name = bind.dialect.name
    if dialect_name == "mysql":
        bind.execute(sa.text(
            """
            INSERT INTO books (project_id, name, order_index, created_at, updated_at)
            SELECT np.id, CONCAT(np.name, ' - 默认书'), 1, NOW(), NOW()
            FROM novel_projects np
            WHERE NOT EXISTS (SELECT 1 FROM books b WHERE b.project_id = np.id)
            """
        ))
        for table_name in (
            "chapters",
            "characters",
            "character_relationships",
            "character_event_participations",
            "chapter_plans",
            "plot_lines",
            "story_events",
            "worldbook_entries",
        ):
            bind.execute(sa.text(
                f"""
                UPDATE {table_name} item
                JOIN (
                    SELECT b.id, b.project_id
                    FROM books b
                    JOIN (
                        SELECT project_id, MIN(order_index) AS min_order, MIN(id) AS min_id
                        FROM books
                        GROUP BY project_id
                    ) picked ON picked.project_id = b.project_id
                        AND picked.min_order = b.order_index
                        AND picked.min_id = b.id
                ) def ON def.project_id = item.project_id
                SET item.book_id = def.id
                WHERE item.book_id IS NULL
                """
            ))
    else:
        bind.execute(sa.text(
            """
            INSERT INTO books (project_id, name, order_index, created_at, updated_at)
            SELECT np.id, np.name || ' - 默认书', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM novel_projects np
            WHERE NOT EXISTS (SELECT 1 FROM books b WHERE b.project_id = np.id)
            """
        ))
        for table_name in (
            "chapters",
            "characters",
            "character_relationships",
            "character_event_participations",
            "chapter_plans",
            "plot_lines",
            "story_events",
            "worldbook_entries",
        ):
            bind.execute(sa.text(
                f"""
                UPDATE {table_name}
                SET book_id = (
                    SELECT b.id
                    FROM books b
                    WHERE b.project_id = {table_name}.project_id
                    ORDER BY b.order_index ASC, b.id ASC
                    LIMIT 1
                )
                WHERE book_id IS NULL
                """
            ))


def downgrade() -> None:
    # Keep downgrade conservative; dropping these columns can destroy user content boundaries.
    pass
