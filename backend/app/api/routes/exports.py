from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.common import ApiResponse
from app.schemas.file import FileContent, FileInfo, FileList, FileUpdateRequest
from app.services.export_service import (
    delete_project_file,
    export_chapter_hierarchy,
    export_hierarchical_markdown,
    export_project_archive,
    export_project_files,
    get_project_file_content,
    list_project_files,
    update_project_file,
)


router = APIRouter()


@router.post("/{project_id}/exports/files", response_model=ApiResponse)
def export_project_files_endpoint(project_id: int, db: Session = Depends(get_db_session)) -> ApiResponse:
    try:
        result = export_project_files(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ApiResponse(message="project files exported", data=result)


@router.post("/{project_id}/exports/chapter-hierarchy", response_model=ApiResponse)
def export_chapter_hierarchy_endpoint(project_id: int, db: Session = Depends(get_db_session)) -> ApiResponse:
    """按"项目→任务→章节→小节→每小节的内容.md"层级结构导出 Markdown
    出口位置优先用 project.export_root_path（用户创建项目时指定），否则用后端默认。
    """
    try:
        result = export_chapter_hierarchy(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ApiResponse(message="chapter hierarchy exported", data=result)


@router.get("/{project_id}/exports/chapter-hierarchy")
def download_chapter_hierarchy_endpoint(project_id: int, db: Session = Depends(get_db_session)) -> FileResponse:
    """下载层级结构 Markdown 归档 ZIP"""
    try:
        result = export_chapter_hierarchy(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FileResponse(
        result["archive_path"],
        media_type="application/zip",
        filename=Path(result["archive_path"]).name,
    )


@router.post("/{project_id}/exports/archive", response_model=ApiResponse)
def export_project_archive_endpoint(project_id: int, db: Session = Depends(get_db_session)) -> ApiResponse:
    try:
        result = export_project_archive(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ApiResponse(message="project archive exported", data=result)


@router.post("/{project_id}/exports/hierarchical-md", response_model=ApiResponse)
def export_hierarchical_markdown_endpoint(project_id: int, db: Session = Depends(get_db_session)) -> ApiResponse:
    """按"书库→主题→风格→题目→章节→内容"层级结构导出 Markdown"""
    try:
        result = export_hierarchical_markdown(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ApiResponse(message="hierarchical markdown exported", data=result)


@router.get("/{project_id}/exports/hierarchical-md")
def download_hierarchical_archive_endpoint(project_id: int, db: Session = Depends(get_db_session)) -> FileResponse:
    """下载层级 Markdown 归档 ZIP"""
    try:
        result = export_hierarchical_markdown(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FileResponse(result["archive_path"], media_type="application/zip", filename=Path(result["archive_path"]).name)


@router.get("/{project_id}/exports/archive")
def download_project_archive_endpoint(project_id: int, db: Session = Depends(get_db_session)) -> FileResponse:
    try:
        result = export_project_archive(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FileResponse(result["archive_path"], media_type="application/zip", filename=Path(result["archive_path"]).name)


@router.get("/{project_id}/files", response_model=ApiResponse)
def list_project_files_endpoint(
    project_id: int,
    file_type: str | None = Query(default=None, description="按文件类型过滤: chapter, asset, log, archive"),
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    """列出项目所有生成的文件"""
    try:
        files = list_project_files(db, project_id, file_type=file_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    file_infos = [FileInfo(**f) for f in files]
    return ApiResponse(
        message="project files listed",
        data=FileList(files=file_infos, total=len(file_infos)),
    )


@router.get("/{project_id}/files/{file_path:path}", response_model=ApiResponse)
def get_project_file_endpoint(
    project_id: int,
    file_path: str,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    """获取指定文件的内容和元数据"""
    try:
        result = get_project_file_content(db, project_id, file_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ApiResponse(
        message="file content retrieved",
        data=FileContent(
            path=result["path"],
            content=result["content"],
            metadata=result["metadata"],
        ),
    )


@router.delete("/{project_id}/files/{file_path:path}", response_model=ApiResponse)
def delete_project_file_endpoint(
    project_id: int,
    file_path: str,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    """删除指定文件（仅限非核心文件）"""
    try:
        result = delete_project_file(db, project_id, file_path)
    except ValueError as exc:
        if "Cannot delete core file" in str(exc):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ApiResponse(message="file deleted", data=result)


@router.put("/{project_id}/files/{file_path:path}", response_model=ApiResponse)
def update_project_file_endpoint(
    project_id: int,
    file_path: str,
    payload: FileUpdateRequest,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    """更新文件内容（仅限章节文件）"""
    try:
        result = update_project_file(
            db,
            project_id,
            file_path,
            new_content=payload.content,
            comment=payload.comment,
        )
    except ValueError as exc:
        if "Only chapter files" in str(exc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ApiResponse(message="file updated", data=result)
