from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CharacterEventParticipationBase(BaseModel):
    character_id: int
    event_id: int
    role_type: str = "participant"
    impact_score: float = 1.0
    note: str | None = None


class CharacterEventParticipationCreate(CharacterEventParticipationBase):
    pass


class CharacterEventParticipationRead(CharacterEventParticipationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    book_id: int | None = None
    created_at: datetime
    updated_at: datetime
