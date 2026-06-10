from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.character import Character
from app.schemas.character import CharacterCreate, CharacterUpdate
from app.services.graph_service import sync_character_to_neo4j


def list_characters(db: Session, project_id: int, book_id: int | None = None) -> list[Character]:
    query = select(Character).where(Character.project_id == project_id)
    if book_id is not None:
        query = query.where(Character.book_id == book_id)
    return list(db.scalars(query.order_by(Character.updated_at.desc())))


def create_character(db: Session, project_id: int, payload: CharacterCreate) -> Character:
    character = Character(project_id=project_id, **payload.model_dump())
    db.add(character)
    db.commit()
    db.refresh(character)
    sync_character_to_neo4j(character)
    return character


def get_character(db: Session, project_id: int, character_id: int) -> Character | None:
    return db.scalar(select(Character).where(Character.project_id == project_id, Character.id == character_id))


def update_character(db: Session, character: Character, payload: CharacterUpdate) -> Character:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(character, field, value)
    db.add(character)
    db.commit()
    db.refresh(character)
    sync_character_to_neo4j(character)
    return character


def delete_character(db: Session, character: Character) -> None:
    db.delete(character)
    db.commit()
