from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.worldbook_entry import WorldbookEntry
from app.schemas.worldbook_entry import WorldbookEntryCreate, WorldbookEntryUpdate
from app.services.graph_service import sync_worldbook_entry_to_neo4j


def list_worldbook_entries(db: Session, project_id: int, book_id: int | None = None) -> list[WorldbookEntry]:
    query = select(WorldbookEntry).where(WorldbookEntry.project_id == project_id)
    if book_id is not None:
        query = query.where(WorldbookEntry.book_id == book_id)
    return list(db.scalars(query.order_by(WorldbookEntry.updated_at.desc())))


def create_worldbook_entry(db: Session, project_id: int, payload: WorldbookEntryCreate) -> WorldbookEntry:
    entry = WorldbookEntry(project_id=project_id, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    sync_worldbook_entry_to_neo4j(entry)
    return entry


def get_worldbook_entry(db: Session, project_id: int, entry_id: int) -> WorldbookEntry | None:
    return db.scalar(select(WorldbookEntry).where(WorldbookEntry.project_id == project_id, WorldbookEntry.id == entry_id))


def update_worldbook_entry(db: Session, entry: WorldbookEntry, payload: WorldbookEntryUpdate) -> WorldbookEntry:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    sync_worldbook_entry_to_neo4j(entry)
    return entry


def delete_worldbook_entry(db: Session, entry: WorldbookEntry) -> None:
    db.delete(entry)
    db.commit()
