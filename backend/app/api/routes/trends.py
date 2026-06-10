from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.common import ApiResponse
from app.schemas.character import CharacterRead
from app.schemas.plot_line import PlotLineRead
from app.schemas.trend_asset_mapping import TrendAssetMappingRequest
from app.schemas.trend_execution import TrendExecutionRequest
from app.schemas.trend_exploration import TrendExplorationCreate, TrendExplorationRead
from app.schemas.worldbook_entry import WorldbookEntryRead
from app.services.trend_asset_mapping_service import map_trend_to_assets
from app.services.trend_service import create_trend, execute_trend_exploration, list_trends


router = APIRouter()


@router.get("/{project_id}/trend-explorations", response_model=ApiResponse)
def read_trends(project_id: int, db: Session = Depends(get_db_session)) -> ApiResponse:
    items = list_trends(db, project_id)
    return ApiResponse(data=[TrendExplorationRead.model_validate(item) for item in items])


@router.post("/{project_id}/trend-explorations", response_model=ApiResponse)
def create_trend_endpoint(
    project_id: int,
    payload: TrendExplorationCreate,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    item = create_trend(db, project_id, payload)
    return ApiResponse(message="trend exploration created", data=TrendExplorationRead.model_validate(item))


@router.post("/{project_id}/trend-explorations/execute", response_model=ApiResponse)
def execute_trend_endpoint(
    project_id: int,
    payload: TrendExecutionRequest,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    try:
        item = execute_trend_exploration(
            db,
            project_id=project_id,
            title=payload.title,
            query_text=payload.query_text,
            source_scope=payload.source_scope,
            search_depth=payload.search_depth,
            max_results=payload.max_results,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(message="trend exploration executed", data=TrendExplorationRead.model_validate(item))


@router.post("/{project_id}/trend-explorations/map-assets", response_model=ApiResponse)
def map_trend_assets_endpoint(
    project_id: int,
    payload: TrendAssetMappingRequest,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    try:
        result = map_trend_to_assets(
            db,
            project_id=project_id,
            trend_id=payload.trend_id,
            create_plot_lines=payload.create_plot_lines,
            create_character_candidates=payload.create_character_candidates,
            create_worldbook_entries=payload.create_worldbook_entries,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ApiResponse(
        message="trend assets mapped",
        data={
            "trend": TrendExplorationRead.model_validate(result["trend"]),
            "plot_lines": [PlotLineRead.model_validate(item) for item in result["plot_lines"]],
            "characters": [CharacterRead.model_validate(item) for item in result["characters"]],
            "worldbook_entries": [WorldbookEntryRead.model_validate(item) for item in result["worldbook_entries"]],
        },
    )
