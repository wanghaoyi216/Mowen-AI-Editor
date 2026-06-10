from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.character import CharacterCreate, CharacterRead, CharacterUpdate
from app.schemas.common import ApiResponse
from app.services.character_service import (
    create_character,
    delete_character,
    get_character,
    list_characters,
    update_character,
)


router = APIRouter()


@router.get("/{project_id}/characters", response_model=ApiResponse)
def read_characters(
    project_id: int,
    book_id: int | None = None,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    items = list_characters(db, project_id, book_id)
    return ApiResponse(data=[CharacterRead.model_validate(item) for item in items])


@router.post("/{project_id}/characters", response_model=ApiResponse)
def create_character_endpoint(
    project_id: int,
    payload: CharacterCreate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = create_character(db, project_id, payload)
    return ApiResponse(message="character created", data=CharacterRead.model_validate(item))


@router.patch("/{project_id}/characters/{character_id}", response_model=ApiResponse)
def update_character_endpoint(
    project_id: int,
    character_id: int,
    payload: CharacterUpdate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = get_character(db, project_id, character_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    updated = update_character(db, item, payload)
    return ApiResponse(message="character updated", data=CharacterRead.model_validate(updated))


@router.delete("/{project_id}/characters/{character_id}", response_model=ApiResponse)
def delete_character_endpoint(
    project_id: int,
    character_id: int,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = get_character(db, project_id, character_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    delete_character(db, item)
    return ApiResponse(message="character deleted", data={"id": character_id})
