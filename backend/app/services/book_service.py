"""Book service — 书籍资源 CRUD + 自动默认书创建。

业务约束：
    - 每个 project 必须至少有 1 本书（``ensure_default_book``）
    - 删除书时仅删除 Book 行本身，content 表 book_id 设为 NULL（保持数据
      完整性，调用方可显式指定迁移策略）
    - 创建 project 时同步创建默认书（``create_default_book_for_project``），
      路由 ``POST /projects`` 调用 ``create_project_with_default_book``
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.book import Book
from app.schemas.book import BookCreate, BookUpdate


logger = logging.getLogger(__name__)


def list_books_for_project(db: Session, project_id: int) -> list[Book]:
    """列出指定 project 下所有 book，按 ``order_index`` 升序。"""
    return list(
        db.scalars(
            select(Book)
            .where(Book.project_id == project_id)
            .order_by(Book.order_index.asc(), Book.id.asc())
        )
    )


def get_book(db: Session, book_id: int) -> Book | None:
    return db.get(Book, book_id)


def create_book(
    db: Session,
    project_id: int,
    payload: BookCreate,
) -> Book:
    """在指定 project 下创建一本书。"""
    book = Book(project_id=project_id, **payload.model_dump())
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def update_book(
    db: Session,
    book: Book,
    payload: BookUpdate,
) -> Book:
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(book, field_name, value)
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def delete_book(db: Session, book: Book) -> None:
    db.delete(book)
    db.commit()


def get_default_book(db: Session, project_id: int) -> Optional[Book]:
    """获取指定 project 的"默认"书（即 ``order_index`` 最小的书）。"""
    return db.scalars(
        select(Book)
        .where(Book.project_id == project_id)
        .order_by(Book.order_index.asc(), Book.id.asc())
        .limit(1)
    ).first()


def ensure_default_book(db: Session, project_id: int, project_name: str | None = None) -> Book:
    """确保 project 至少有一本书；若无则创建 "默认书"。

    主要用于项目创建后首次访问书籍资源的兜底；正常路径上
    ``create_project_with_default_book`` 已经创建过默认书。
    """
    existing = get_default_book(db, project_id)
    if existing is not None:
        return existing
    default_name = f"{(project_name or '新项目')[:150]} - 默认书"
    book = Book(project_id=project_id, name=default_name, order_index=1)
    db.add(book)
    db.commit()
    db.refresh(book)
    logger.info("[book] ensure_default_book created: project_id=%s, book_id=%s", project_id, book.id)
    return book
