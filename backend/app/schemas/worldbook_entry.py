from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WorldbookEntryBase(BaseModel):
    book_id: int | None = None
    title: str
    category: str = "setting"
    content: str
    source_type: str | None = None
    source_ref: str | None = None


class WorldbookEntryCreate(WorldbookEntryBase):
    pass


class WorldbookEntryUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    content: str | None = None
    source_type: str | None = None
    source_ref: str | None = None


class WorldbookEntryRead(WorldbookEntryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
