from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlotLineBase(BaseModel):
    book_id: int | None = None
    chapter_id: int | None = None
    title: str
    plot_type: str = "main"
    summary: str | None = None
    goal: str | None = None
    conflict: str | None = None
    stakes: str | None = None
    start_phase: str | None = None
    end_phase: str | None = None
    status: str = "planned"
    priority: int = 0
    scene_order: int = 0


class PlotLineCreate(PlotLineBase):
    pass


class PlotLineUpdate(BaseModel):
    book_id: int | None = None
    chapter_id: int | None = None
    title: str | None = None
    plot_type: str | None = None
    summary: str | None = None
    goal: str | None = None
    conflict: str | None = None
    stakes: str | None = None
    start_phase: str | None = None
    end_phase: str | None = None
    status: str | None = None
    priority: int | None = None
    scene_order: int | None = None


class PlotLineRead(PlotLineBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
