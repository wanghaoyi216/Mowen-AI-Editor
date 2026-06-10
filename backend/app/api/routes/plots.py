from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.common import ApiResponse
from app.schemas.plot_line import PlotLineCreate, PlotLineRead, PlotLineUpdate
from app.schemas.story_event import StoryEventCreate, StoryEventRead
from app.services.plot_service import (
    create_plot_line,
    create_story_event,
    delete_plot_line,
    delete_story_event,
    get_plot_line,
    get_story_event,
    list_plot_lines,
    list_story_events,
    update_plot_line,
    update_story_event,
)


router = APIRouter()


@router.get("/{project_id}/plot-lines", response_model=ApiResponse)
def read_plot_lines(
    project_id: int,
    book_id: int | None = None,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    items = list_plot_lines(db, project_id, book_id)
    return ApiResponse(data=[PlotLineRead.model_validate(item) for item in items])


@router.post("/{project_id}/plot-lines", response_model=ApiResponse)
def create_plot_line_endpoint(
    project_id: int,
    payload: PlotLineCreate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = create_plot_line(db, project_id, payload)
    return ApiResponse(message="plot line created", data=PlotLineRead.model_validate(item))


@router.patch("/{project_id}/plot-lines/{plot_line_id}", response_model=ApiResponse)
def update_plot_line_endpoint(
    project_id: int,
    plot_line_id: int,
    payload: PlotLineUpdate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = get_plot_line(db, project_id, plot_line_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot line not found")
    updated = update_plot_line(db, item, payload)
    return ApiResponse(message="plot line updated", data=PlotLineRead.model_validate(updated))


@router.delete("/{project_id}/plot-lines/{plot_line_id}", response_model=ApiResponse)
def delete_plot_line_endpoint(
    project_id: int,
    plot_line_id: int,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = get_plot_line(db, project_id, plot_line_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot line not found")
    delete_plot_line(db, item)
    return ApiResponse(message="plot line deleted", data={"id": plot_line_id})


@router.get("/{project_id}/events", response_model=ApiResponse)
def read_story_events(
    project_id: int,
    plot_line_id: int | None = None,
    book_id: int | None = None,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    items = list_story_events(db, project_id, plot_line_id, book_id)
    return ApiResponse(data=[StoryEventRead.model_validate(item) for item in items])


@router.get("/{project_id}/events/{event_id}", response_model=ApiResponse)
def read_story_event(
    project_id: int,
    event_id: int,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = get_story_event(db, project_id, event_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story event not found")
    return ApiResponse(data=StoryEventRead.model_validate(item))


@router.patch("/{project_id}/events/{event_id}", response_model=ApiResponse)
def update_story_event_endpoint(
    project_id: int,
    event_id: int,
    payload: StoryEventCreate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = get_story_event(db, project_id, event_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story event not found")
    updated = update_story_event(db, item, payload)
    return ApiResponse(message="story event updated", data=StoryEventRead.model_validate(updated))


@router.delete("/{project_id}/events/{event_id}", response_model=ApiResponse)
def delete_story_event_endpoint(
    project_id: int,
    event_id: int,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = get_story_event(db, project_id, event_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story event not found")
    delete_story_event(db, item)
    return ApiResponse(message="story event deleted", data={"id": event_id})


@router.post("/{project_id}/events", response_model=ApiResponse)
def create_story_event_endpoint(
    project_id: int,
    payload: StoryEventCreate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = create_story_event(db, project_id, payload)
    return ApiResponse(message="story event created", data=StoryEventRead.model_validate(item))
