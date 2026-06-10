from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChapterVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    chapter_id: int
    version_no: int
    operation_type: str
    instruction: str | None = None
    consistency_report: str | None = None
    content: str
    summary: str | None = None
    selected_model: str | None = None
    created_at: datetime


class ChapterRevisionRequest(BaseModel):
    revision_focus: str | None = None
    style_hint: str | None = None
    # None → 由项目级字数区间推导目标字数
    word_target: int | None = None
