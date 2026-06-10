from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.chapter_version import ChapterVersion
from app.schemas.chapter import ChapterCreate


def list_chapters(db: Session, project_id: int, book_id: int | None = None) -> list[Chapter]:
    query = select(Chapter).where(Chapter.project_id == project_id)
    if book_id is not None:
        query = query.where(Chapter.book_id == book_id)
    return list(db.scalars(query.order_by(Chapter.chapter_no.asc())))


def create_chapter(db: Session, project_id: int, payload: ChapterCreate) -> Chapter:
    chapter = Chapter(project_id=project_id, **payload.model_dump())
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return chapter


def get_chapter(db: Session, project_id: int, chapter_id: int) -> Chapter | None:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.project_id != project_id:
        return None
    return chapter


def list_chapter_versions(db: Session, project_id: int, chapter_id: int) -> list[ChapterVersion]:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.project_id != project_id:
        return []
    return list(
        db.scalars(
            select(ChapterVersion)
            .where(ChapterVersion.project_id == project_id, ChapterVersion.chapter_id == chapter_id)
            .order_by(ChapterVersion.version_no.desc(), ChapterVersion.created_at.desc())
        )
    )
