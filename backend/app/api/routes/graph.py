from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.routes._guards import get_owned_project
from app.models.project import NovelProject
from app.schemas.common import ApiResponse
from app.schemas.graph import CharacterRelationshipCreate, CharacterRelationshipRead, GraphRead
from app.services.graph_service import create_character_relationship, get_project_graph
from app.services.story_graph_generation_service import generate_normalized_story_graph


router = APIRouter()


@router.get("/{project_id}/graph", response_model=ApiResponse)
def get_graph(
    project_id: int,
    graph_type: str = "story_entity",
    chapter_id: int | None = None,
    character_id: int | None = None,
    book_id: int | None = None,
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> ApiResponse:
    graph_data = get_project_graph(
        db, project_id, character_id, chapter_id, graph_type, book_id
    )
    nodes = graph_data["nodes"] or []
    # A1.4: nodes 为空时区分 empty_book / empty_project，供前端切换提示语
    hint: str | None = None
    if len(nodes) == 0:
        hint = "empty_book" if book_id else "empty_project"
    return ApiResponse(
        data=GraphRead(
            project_id=project_id,
            graph_type=graph_type,
            filters={"chapter_id": chapter_id, "character_id": character_id, "book_id": book_id},
            source=graph_data["source"],
            nodes=nodes,
            relationships=graph_data["relationships"],
            generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            hint=hint,
        )
    )


@router.post("/{project_id}/graph/generate", response_model=ApiResponse)
def generate_graph(
    project_id: int,
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> ApiResponse:
    """AI 分析项目已有角色/剧情/世界观，生成人物关系、故事弧线、关键事件、
    主题连接，写入数据库并同步 Neo4j。供前端"生成故事图谱"按钮调用。"""
    try:
        summary = generate_normalized_story_graph(db, project_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)[:300]) from exc
    return ApiResponse(message="knowledge graph generated", data=summary)


@router.post("/{project_id}/graph/relationships", response_model=ApiResponse)
def create_relationship(
    project_id: int,
    payload: CharacterRelationshipCreate,
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> ApiResponse:
    try:
        item = create_character_relationship(db, project_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(message="relationship created", data=CharacterRelationshipRead.model_validate(item))
