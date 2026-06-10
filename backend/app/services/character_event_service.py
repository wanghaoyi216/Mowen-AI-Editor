from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.character import Character
from app.models.character_event_participation import CharacterEventParticipation
from app.models.story_event import StoryEvent
from app.schemas.character_event import CharacterEventParticipationCreate
from app.services.graph_service import sync_character_event_participation_to_neo4j


def list_event_participations(
    db: Session,
    project_id: int,
    event_id: int | None = None,
    book_id: int | None = None,
) -> list[CharacterEventParticipation]:
    query = select(CharacterEventParticipation).where(CharacterEventParticipation.project_id == project_id)
    if event_id is not None:
        query = query.where(CharacterEventParticipation.event_id == event_id)
    if book_id is not None:
        query = query.where(CharacterEventParticipation.book_id == book_id)
    return list(db.scalars(query.order_by(CharacterEventParticipation.updated_at.desc())))


def create_event_participation(
    db: Session,
    project_id: int,
    payload: CharacterEventParticipationCreate,
) -> CharacterEventParticipation:
    character = db.get(Character, payload.character_id)
    event = db.get(StoryEvent, payload.event_id)
    if character is None or event is None:
        raise ValueError("Character or event not found")
    if character.project_id != project_id or event.project_id != project_id:
        raise ValueError("Character and event must belong to the same project")
    if character.book_id is not None and event.book_id is not None and character.book_id != event.book_id:
        raise ValueError("Character and event must belong to the same book")

    item = CharacterEventParticipation(
        project_id=project_id,
        book_id=event.book_id or character.book_id,
        **payload.model_dump(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    sync_character_event_participation_to_neo4j(item)
    return item


def get_event_participation(db: Session, project_id: int, participation_id: int) -> CharacterEventParticipation | None:
    return db.scalar(
        select(CharacterEventParticipation).where(
            CharacterEventParticipation.project_id == project_id,
            CharacterEventParticipation.id == participation_id,
        )
    )


def update_event_participation(
    db: Session,
    participation: CharacterEventParticipation,
    payload: CharacterEventParticipationCreate,
) -> CharacterEventParticipation:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(participation, field, value)
    db.add(participation)
    db.commit()
    db.refresh(participation)
    sync_character_event_participation_to_neo4j(participation)
    return participation


def delete_event_participation(db: Session, participation: CharacterEventParticipation) -> None:
    db.delete(participation)
    db.commit()
