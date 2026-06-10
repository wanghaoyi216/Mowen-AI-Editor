from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StoryEventBase(BaseModel):
    book_id: int | None = None
    plot_line_id: int | None = None
    chapter_id: int | None = None
    title: str
    event_type: str = "scene"
    summary: str | None = None
    trigger_condition: str | None = None
    expected_outcome: str | None = None
    impact_level: int = 1
    status: str = "planned"


class StoryEventCreate(StoryEventBase):
    pass


class StoryEventRead(StoryEventBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
