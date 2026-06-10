from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CharacterBase(BaseModel):
    name: str
    alias: str | None = None
    role_type: str | None = None
    gender: str | None = None
    age: int | None = None
    identity: str | None = None
    personality: str | None = None
    motivation: str | None = None
    goal: str | None = None
    fear: str | None = None
    secret: str | None = None
    background: str | None = None
    appearance: str | None = None
    status: str = "active"
    arc_summary: str | None = None
    book_id: int | None = None


class CharacterCreate(CharacterBase):
    pass


class CharacterUpdate(BaseModel):
    name: str | None = None
    alias: str | None = None
    role_type: str | None = None
    gender: str | None = None
    age: int | None = None
    identity: str | None = None
    personality: str | None = None
    motivation: str | None = None
    goal: str | None = None
    fear: str | None = None
    secret: str | None = None
    background: str | None = None
    appearance: str | None = None
    status: str | None = None
    arc_summary: str | None = None


class CharacterRead(CharacterBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
