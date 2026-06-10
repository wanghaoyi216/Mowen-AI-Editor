from pydantic import BaseModel, Field


class EntityExtractionRequest(BaseModel):
    text: str
    source_type: str = "manual"
    source_ref: str | None = None
    task_id: int | None = None
    use_llm: bool = False


class EntityExtractionSummary(BaseModel):
    added_entities: int = 0
    updated_entities: int = 0
    added_relationships: int = 0
    updated_relationships: int = 0
    characters: list[str] = Field(default_factory=list)
    worldbook_entries: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)

