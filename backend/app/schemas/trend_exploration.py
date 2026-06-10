from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TrendExplorationBase(BaseModel):
    title: str
    source_scope: str | None = None
    query_text: str
    raw_findings: str | None = None
    extracted_topics: str | None = None
    extracted_tags: str | None = None
    suggested_directions: str | None = None
    status: str = "draft"


class TrendExplorationCreate(TrendExplorationBase):
    pass


class TrendExplorationRead(TrendExplorationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
