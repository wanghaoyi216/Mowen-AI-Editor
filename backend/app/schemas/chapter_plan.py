from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChapterPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    book_id: int | None = None
    chapter_id: int
    plot_line_id: int | None = None
    title: str
    design_brief: str
    beat_sheet: str
    asset_summary: str
    selected_model: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class ChapterDesignRequest(BaseModel):
    plot_line_id: int | None = None
    guidance: str | None = None


class ChapterGenerateRequest(BaseModel):
    style_hint: str | None = None
    # None → 由项目级字数区间(min/max words per chapter)推导目标字数
    word_target: int | None = None
