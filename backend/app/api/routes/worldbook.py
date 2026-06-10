from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.common import ApiResponse
from app.schemas.worldbook_entry import WorldbookEntryCreate, WorldbookEntryRead, WorldbookEntryUpdate
from app.services.worldbook_service import (
    create_worldbook_entry,
    delete_worldbook_entry,
    get_worldbook_entry,
    list_worldbook_entries,
    update_worldbook_entry,
)


router = APIRouter()


@router.get("/{project_id}/worldbook", response_model=ApiResponse)
def read_worldbook_entries(
    project_id: int,
    book_id: int | None = None,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    items = list_worldbook_entries(db, project_id, book_id)
    return ApiResponse(data=[WorldbookEntryRead.model_validate(item) for item in items])


@router.post("/{project_id}/worldbook", response_model=ApiResponse)
def create_worldbook_entry_endpoint(
    project_id: int,
    payload: WorldbookEntryCreate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = create_worldbook_entry(db, project_id, payload)
    return ApiResponse(message="worldbook entry created", data=WorldbookEntryRead.model_validate(item))


@router.patch("/{project_id}/worldbook/{entry_id}", response_model=ApiResponse)
def update_worldbook_entry_endpoint(
    project_id: int,
    entry_id: int,
    payload: WorldbookEntryUpdate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = get_worldbook_entry(db, project_id, entry_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worldbook entry not found")
    updated = update_worldbook_entry(db, item, payload)
    return ApiResponse(message="worldbook entry updated", data=WorldbookEntryRead.model_validate(updated))


@router.delete("/{project_id}/worldbook/{entry_id}", response_model=ApiResponse)
def delete_worldbook_entry_endpoint(
    project_id: int,
    entry_id: int,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = get_worldbook_entry(db, project_id, entry_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worldbook entry not found")
    delete_worldbook_entry(db, item)
    return ApiResponse(message="worldbook entry deleted", data={"id": entry_id})
