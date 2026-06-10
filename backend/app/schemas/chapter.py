from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChapterBase(BaseModel):
    book_id: int | None = None
    chapter_no: int
    title: str
    summary: str | None = None
    objective: str | None = None
    conflict: str | None = None
    status: str = "planned"
    draft_content: str | None = None
    final_content: str | None = None
    word_count: int = 0
    version: int = 1


class ChapterCreate(ChapterBase):
    pass


class ChapterRead(ChapterBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
