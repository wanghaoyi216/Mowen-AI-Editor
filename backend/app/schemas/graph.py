from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GraphNode(BaseModel):
    id: str
    entity_id: int
    label: str
    type: str
    meta: dict = Field(default_factory=dict)


class GraphRelationship(BaseModel):
    id: str
    source: str
    target: str
    type: str
    meta: dict = Field(default_factory=dict)


class CharacterRelationshipBase(BaseModel):
    book_id: int | None = None
    source_character_id: int
    target_character_id: int
    relation_type: str
    intensity: float = 1.0
    status: str = "active"
    note: str | None = None


class CharacterRelationshipCreate(CharacterRelationshipBase):
    pass


class CharacterRelationshipRead(CharacterRelationshipBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    book_id: int | None = None
    created_at: datetime
    updated_at: datetime


class GraphRead(BaseModel):
    project_id: int
    graph_type: str
    filters: dict
    source: str
    nodes: list[GraphNode] = Field(default_factory=list)
    relationships: list[GraphRelationship] = Field(default_factory=list)
    generated_at: str | None = None
    hint: str | None = None
