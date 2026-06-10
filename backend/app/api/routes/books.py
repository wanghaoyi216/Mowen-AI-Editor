"""Book API routes — 书籍资源 CRUD。

端点：
  * ``POST   /projects/{project_id}/books``   — 在项目下新建一本书
  * ``GET    /projects/{project_id}/books``   — 列出项目下所有书
  * ``PATCH  /books/{book_id}``               — 修改书名/描述/order_index
  * ``DELETE /books/{book_id}``               — 删除书（仅删 Book 行本身）

所有端点共用 ``ApiResponse`` 包装；返回 dict 直接 ``model_validate``。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.models.project import NovelProject
from app.schemas.book import (
    BookCreate,
    BookListResponse,
    BookOut,
    BookUpdate,
)
from app.schemas.common import ApiResponse
from app.services.book_service import (
    create_book,
    delete_book,
    get_book,
    list_books_for_project,
    update_book,
)


# 子路由：``/projects/{id}/books`` 与 ``/books/{id}`` 共用同一文件
project_books_router = APIRouter(prefix="/projects", tags=["books"])
book_router = APIRouter(prefix="/books", tags=["books"])


@project_books_router.post(
    "/{project_id}/books",
    response_model=ApiResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_book_endpoint(
    project_id: int,
    payload: BookCreate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    if db.get(NovelProject, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    book = create_book(db, project_id, payload)
    return ApiResponse(message="book created", data=BookOut.model_validate(book))


@project_books_router.get(
    "/{project_id}/books",
    response_model=ApiResponse,
)
def list_books_endpoint(
    project_id: int,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    if db.get(NovelProject, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    items = list_books_for_project(db, project_id)
    out_items = [BookOut.model_validate(b) for b in items]
    return ApiResponse(
        data=BookListResponse(project_id=project_id, books=out_items, total=len(out_items))
    )


@book_router.patch(
    "/{book_id}",
    response_model=ApiResponse,
)
def update_book_endpoint(
    book_id: int,
    payload: BookUpdate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    book = get_book(db, book_id)
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    updated = update_book(db, book, payload)
    return ApiResponse(message="book updated", data=BookOut.model_validate(updated))


@book_router.delete(
    "/{book_id}",
    response_model=ApiResponse,
)
def delete_book_endpoint(
    book_id: int,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    book = get_book(db, book_id)
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    delete_book(db, book)
    return ApiResponse(message="book deleted", data={"id": book_id})
