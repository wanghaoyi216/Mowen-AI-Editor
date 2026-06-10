from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plot_line import PlotLine
from app.models.story_event import StoryEvent
from app.schemas.plot_line import PlotLineCreate, PlotLineUpdate
from app.schemas.story_event import StoryEventCreate
from app.services.graph_service import sync_plot_line_to_neo4j, sync_story_event_to_neo4j


def list_plot_lines(db: Session, project_id: int, book_id: int | None = None) -> list[PlotLine]:
    query = select(PlotLine).where(PlotLine.project_id == project_id)
    if book_id is not None:
        query = query.where(PlotLine.book_id == book_id)
    return list(db.scalars(query.order_by(PlotLine.priority.desc())))


def create_plot_line(db: Session, project_id: int, payload: PlotLineCreate) -> PlotLine:
    plot_line = PlotLine(project_id=project_id, **payload.model_dump())
    db.add(plot_line)
    db.commit()
    db.refresh(plot_line)
    sync_plot_line_to_neo4j(plot_line)
    return plot_line


def get_plot_line(db: Session, project_id: int, plot_line_id: int) -> PlotLine | None:
    return db.scalar(select(PlotLine).where(PlotLine.project_id == project_id, PlotLine.id == plot_line_id))


def update_plot_line(db: Session, plot_line: PlotLine, payload: PlotLineUpdate) -> PlotLine:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plot_line, field, value)
    db.add(plot_line)
    db.commit()
    db.refresh(plot_line)
    sync_plot_line_to_neo4j(plot_line)
    return plot_line


def delete_plot_line(db: Session, plot_line: PlotLine) -> None:
    db.delete(plot_line)
    db.commit()


def list_story_events(
    db: Session,
    project_id: int,
    plot_line_id: int | None = None,
    book_id: int | None = None,
) -> list[StoryEvent]:
    query = select(StoryEvent).where(StoryEvent.project_id == project_id)
    if plot_line_id is not None:
        query = query.where(StoryEvent.plot_line_id == plot_line_id)
    if book_id is not None:
        query = query.where(StoryEvent.book_id == book_id)
    return list(db.scalars(query.order_by(StoryEvent.updated_at.desc())))


def create_story_event(db: Session, project_id: int, payload: StoryEventCreate) -> StoryEvent:
    story_event = StoryEvent(project_id=project_id, **payload.model_dump())
    db.add(story_event)
    db.commit()
    db.refresh(story_event)
    sync_story_event_to_neo4j(story_event)
    return story_event


def get_story_event(db: Session, project_id: int, event_id: int) -> StoryEvent | None:
    return db.scalar(select(StoryEvent).where(StoryEvent.project_id == project_id, StoryEvent.id == event_id))


def update_story_event(db: Session, story_event: StoryEvent, payload: StoryEventCreate) -> StoryEvent:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(story_event, field, value)
    db.add(story_event)
    db.commit()
    db.refresh(story_event)
    sync_story_event_to_neo4j(story_event)
    return story_event


def delete_story_event(db: Session, story_event: StoryEvent) -> None:
    db.delete(story_event)
    db.commit()
