from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.common import ApiResponse
from app.schemas.entity_extraction import EntityExtractionRequest, EntityExtractionSummary
from app.services.entity_extraction_service import extract_entities_from_text


router = APIRouter()


@router.post("/{project_id}/entity-extraction/extract", response_model=ApiResponse)
def extract_entities_endpoint(
    project_id: int,
    payload: EntityExtractionRequest,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    if not payload.text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Text is required")
    result = extract_entities_from_text(db, project_id, payload)
    return ApiResponse(message="entities extracted and stored", data=EntityExtractionSummary(**result))

