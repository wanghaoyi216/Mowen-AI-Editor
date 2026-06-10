from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.routes._guards import get_owned_project
from app.models.project import NovelProject
from app.schemas.chapter import ChapterCreate, ChapterRead
from app.schemas.chapter_consistency import ChapterConsistencyRead
from app.schemas.chapter_plan import ChapterDesignRequest, ChapterGenerateRequest, ChapterPlanRead
from app.schemas.chapter_version import ChapterRevisionRequest, ChapterVersionRead
from app.schemas.common import ApiResponse
from app.services.chapter_ai_service import build_chapter_plan, generate_chapter_draft
from app.services.chapter_consistency_task_service import execute_chapter_consistency_task
from app.services.chapter_export_service import SUPPORTED_FORMATS, render_chapter
from app.services.chapter_task_service import (
    execute_chapter_design_task,
    execute_chapter_generate_task,
    execute_chapter_revision_task,
)
from app.services.chapter_service import create_chapter, get_chapter, list_chapter_versions, list_chapters


router = APIRouter()


def _safe_download_name(value: str) -> str:
    return "".join("_" if char in '<>:"/\\|?*' else char for char in value).strip() or "chapter"


@router.get("/{project_id}/chapters", response_model=ApiResponse)
def read_chapters(
    project_id: int,
    book_id: int | None = None,
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> ApiResponse:
    items = list_chapters(db, project_id, book_id)
    return ApiResponse(data=[ChapterRead.model_validate(item) for item in items])


@router.post("/{project_id}/chapters", response_model=ApiResponse)
def create_chapter_endpoint(
    project_id: int,
    payload: ChapterCreate,
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> ApiResponse:
    item = create_chapter(db, project_id, payload)
    return ApiResponse(message="chapter created", data=ChapterRead.model_validate(item))


@router.get("/{project_id}/chapters/{chapter_id:int}", response_model=ApiResponse)
def read_chapter(
    project_id: int,
    chapter_id: int,
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> ApiResponse:
    item = get_chapter(db, project_id, chapter_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    return ApiResponse(data=ChapterRead.model_validate(item))


@router.get("/{project_id}/chapters/{chapter_id:int}/export")
def export_chapter_endpoint(
    project_id: int,
    chapter_id: int,
    format: str = Query(
        "md",
        description="导出格式: md | docx | pdf | txt",
        pattern=f"^({'|'.join(SUPPORTED_FORMATS)})$",
    ),
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> Response:
    item = get_chapter(db, project_id, chapter_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

    data, media_type, filename = render_chapter(db, item, format=format)
    encoded_name = quote(filename)
    # HTTP header 必须是 latin-1（ASCII 安全），所以用 filename*=UTF-8''...
    # RFC 5987 / RFC 6266，浏览器自动回落到 ascii 段
    ascii_fallback = filename.encode("ascii", "replace").decode("ascii")
    headers = {
        "Content-Disposition": (
            f'attachment; filename="{ascii_fallback}"; '
            f"filename*=UTF-8''{encoded_name}"
        )
    }
    return Response(content=data, media_type=media_type, headers=headers)


@router.get("/{project_id}/chapters/{chapter_id:int}/export/formats", response_model=ApiResponse)
def export_chapter_formats() -> ApiResponse:
    """列出章节导出支持的所有格式。"""
    return ApiResponse(
        message="supported export formats",
        data={"formats": list(SUPPORTED_FORMATS)},
    )


@router.get("/{project_id}/chapters/{chapter_id:int}/versions", response_model=ApiResponse)
def read_chapter_versions(
    project_id: int,
    chapter_id: int,
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> ApiResponse:
    items = list_chapter_versions(db, project_id, chapter_id)
    return ApiResponse(data=[ChapterVersionRead.model_validate(item) for item in items])


@router.post("/{project_id}/chapters/{chapter_id:int}/design", response_model=ApiResponse)
def design_chapter_endpoint(
    project_id: int,
    chapter_id: int,
    payload: ChapterDesignRequest,
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> ApiResponse:
    try:
        item = build_chapter_plan(
            db,
            project_id=project_id,
            chapter_id=chapter_id,
            plot_line_id=payload.plot_line_id,
            guidance=payload.guidance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(message="chapter designed", data=ChapterPlanRead.model_validate(item))


@router.post("/{project_id}/chapters/{chapter_id:int}/generate", response_model=ApiResponse)
def generate_chapter_endpoint(
    project_id: int,
    chapter_id: int,
    payload: ChapterGenerateRequest,
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> ApiResponse:
    try:
        item = generate_chapter_draft(
            db,
            project_id=project_id,
            chapter_id=chapter_id,
            style_hint=payload.style_hint,
            word_target=payload.word_target,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(message="chapter draft generated", data=ChapterRead.model_validate(item))


@router.post("/{project_id}/chapters/{chapter_id:int}/design-task", response_model=ApiResponse)
def design_chapter_task_endpoint(
    project_id: int,
    chapter_id: int,
    payload: ChapterDesignRequest,
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> ApiResponse:
    try:
        result = execute_chapter_design_task(
            db,
            project_id=project_id,
            chapter_id=chapter_id,
            plot_line_id=payload.plot_line_id,
            guidance=payload.guidance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(
        message="chapter design task executed",
        data={
            "task_id": result["task"].id,
            "plan": ChapterPlanRead.model_validate(result["plan"]),
        },
    )


@router.post("/{project_id}/chapters/{chapter_id:int}/generate-task", response_model=ApiResponse)
def generate_chapter_task_endpoint(
    project_id: int,
    chapter_id: int,
    payload: ChapterGenerateRequest,
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> ApiResponse:
    try:
        result = execute_chapter_generate_task(
            db,
            project_id=project_id,
            chapter_id=chapter_id,
            style_hint=payload.style_hint,
            word_target=payload.word_target,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(
        message="chapter generate task executed",
        data={
            "task_id": result["task"].id,
            "chapter": ChapterRead.model_validate(result["chapter"]),
        },
    )


@router.post("/{project_id}/chapters/{chapter_id:int}/consistency-check", response_model=ApiResponse)
def consistency_check_chapter_endpoint(
    project_id: int,
    chapter_id: int,
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> ApiResponse:
    try:
        result = execute_chapter_consistency_task(db, project_id, chapter_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(
        message="chapter consistency check completed",
        data=ChapterConsistencyRead(
            task_id=result["task"].id,
            model=result["model"],
            report=result["report"],
        ),
    )


@router.post("/{project_id}/chapters/{chapter_id:int}/revise-task", response_model=ApiResponse)
def revise_chapter_task_endpoint(
    project_id: int,
    chapter_id: int,
    payload: ChapterRevisionRequest,
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> ApiResponse:
    try:
        result = execute_chapter_revision_task(db, project_id, chapter_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(
        message="chapter revision task executed",
        data={
            "task_id": result["task"].id,
            "chapter": ChapterRead.model_validate(result["chapter"]),
            "version": ChapterVersionRead.model_validate(result["version"]),
            "consistency_report": result["consistency_report"],
            "consistency_model": result["consistency_model"],
            "rewrite_model": result["rewrite_model"],
            "entity_extraction": result["entity_extraction"],
        },
    )
