from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.character_event import CharacterEventParticipationCreate, CharacterEventParticipationRead
from app.schemas.common import ApiResponse
from app.services.character_event_service import (
    create_event_participation,
    delete_event_participation,
    get_event_participation,
    list_event_participations,
    update_event_participation,
)


router = APIRouter()


@router.get("/{project_id}/event-participations", response_model=ApiResponse)
def read_event_participations(
    project_id: int,
    event_id: int | None = None,
    book_id: int | None = None,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    items = list_event_participations(db, project_id, event_id, book_id)
    return ApiResponse(data=[CharacterEventParticipationRead.model_validate(item) for item in items])


@router.get("/{project_id}/event-participations/{participation_id}", response_model=ApiResponse)
def read_event_participation(
    project_id: int,
    participation_id: int,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = get_event_participation(db, project_id, participation_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event participation not found")
    return ApiResponse(data=CharacterEventParticipationRead.model_validate(item))


@router.patch("/{project_id}/event-participations/{participation_id}", response_model=ApiResponse)
def update_event_participation_endpoint(
    project_id: int,
    participation_id: int,
    payload: CharacterEventParticipationCreate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    try:
        item = get_event_participation(db, project_id, participation_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event participation not found")
        updated = update_event_participation(db, item, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(message="event participation updated", data=CharacterEventParticipationRead.model_validate(updated))


@router.delete("/{project_id}/event-participations/{participation_id}", response_model=ApiResponse)
def delete_event_participation_endpoint(
    project_id: int,
    participation_id: int,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = get_event_participation(db, project_id, participation_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event participation not found")
    delete_event_participation(db, item)
    return ApiResponse(message="event participation deleted", data={"id": participation_id})


@router.post("/{project_id}/event-participations", response_model=ApiResponse)
def create_event_participation_endpoint(
    project_id: int,
    payload: CharacterEventParticipationCreate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    try:
        item = create_event_participation(db, project_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(message="event participation created", data=CharacterEventParticipationRead.model_validate(item))
