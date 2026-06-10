from fastapi import APIRouter, HTTPException, status

from app.schemas.common import ApiResponse
from app.schemas.openrouter import OpenRouterModelRead, OpenRouterModelSelectionRead
from app.services.openrouter_service import get_openrouter_free_models


router = APIRouter()


@router.get("/models/free", response_model=ApiResponse)
def read_openrouter_free_models() -> ApiResponse:
    try:
        result = get_openrouter_free_models()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    selected = result["selected_model"]
    free_models = result["free_models"]
    return ApiResponse(
        data=OpenRouterModelSelectionRead(
            selected_model=OpenRouterModelRead.model_validate(selected) if selected else None,
            free_models=[OpenRouterModelRead.model_validate(item) for item in free_models],
        )
    )
