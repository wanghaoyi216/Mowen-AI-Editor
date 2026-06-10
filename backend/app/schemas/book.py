"""Book Pydantic schemas — 书籍资源 CRUD。

每本书（``Book``）隶属于某个 ``NovelProject``，并通过 ``book_id`` 外键隔离
所有下游内容（chapters / characters / relationships / plot_lines / worldbook）。

典型用法：
    - ``POST /projects/{id}/books`` 创建新书（项目下默认已有 1 本）
    - ``GET /projects/{id}/books`` 列出项目下所有书
    - ``PATCH /books/{id}`` 改书名 / 描述 / order_index
    - ``DELETE /books/{id}`` 删除书（不会级联删除关联章节/角色）

回填说明：
    数据库迁移 ``2026_06_04_add_books.sql`` 会给每个 project 自动创建一个
    "原项目名 - 默认书" 的 book 并把所有现有 content 的 ``book_id`` 指向它。
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BookBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    order_index: int = Field(default=1, ge=0)


class BookCreate(BookBase):
    """``POST /projects/{id}/books`` 请求体。``project_id`` 取自路径参数。"""
    pass


class BookUpdate(BaseModel):
    """``PATCH /books/{id}`` 请求体——所有字段可选。"""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    order_index: int | None = Field(default=None, ge=0)


class BookOut(BookBase):
    """``Book`` ORM 读模型。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BookListResponse(BaseModel):
    """``GET /projects/{id}/books`` 列表响应。"""
    project_id: int
    books: list[BookOut] = Field(default_factory=list)
    total: int = 0
