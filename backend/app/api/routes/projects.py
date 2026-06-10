"""Projects API ── 多用户隔离版。

所有路由都通过 ``Depends(get_current_user_id)`` 拿到当前 user_id，
service 层负责按 owner_id/user_id 过滤；不同用户看不到对方的项目。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db_session
from app.models.project import NovelProject
from app.schemas.common import ApiResponse
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_service import (
    create_project,
    delete_project,
    get_project_for_user,
    list_projects_for_user,
    update_project,
)


router = APIRouter()


def _get_owned_project(db: Session, project_id: int, user_id: int) -> NovelProject:
    """取一条属于当前用户的项目；不属于或不存在都返回 404。"""
    project = get_project_for_user(db, project_id, user_id)
    if project is None:
        # 不暴露"存在但不属于你"和"不存在"的区别，统一 404
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("", response_model=ApiResponse)
def read_projects(
    db: Session = Depends(get_db_session),
    user_id: int = Depends(get_current_user_id),
) -> ApiResponse:
    """列出**当前用户**的项目（不返回别人的）。"""
    projects = list_projects_for_user(db, user_id)
    return ApiResponse(data=[ProjectRead.model_validate(project) for project in projects])


@router.post("", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_project_endpoint(
    payload: ProjectCreate,
    db: Session = Depends(get_db_session),
    user_id: int = Depends(get_current_user_id),
) -> ApiResponse:
    """创建项目，自动绑定 owner_id=user_id。"""
    project = create_project(db, payload, owner_id=user_id)
    return ApiResponse(message="project created", data=ProjectRead.model_validate(project))


@router.get("/{project_id}", response_model=ApiResponse)
def read_project(
    project_id: int,
    db: Session = Depends(get_db_session),
    user_id: int = Depends(get_current_user_id),
) -> ApiResponse:
    project = _get_owned_project(db, project_id, user_id)
    return ApiResponse(data=ProjectRead.model_validate(project))


@router.patch("/{project_id}", response_model=ApiResponse)
def update_project_endpoint(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db_session),
    user_id: int = Depends(get_current_user_id),
) -> ApiResponse:
    project = _get_owned_project(db, project_id, user_id)
    updated = update_project(db, project, payload)
    return ApiResponse(message="project updated", data=ProjectRead.model_validate(updated))


@router.delete("/{project_id}", response_model=ApiResponse)
def delete_project_endpoint(
    project_id: int,
    db: Session = Depends(get_db_session),
    user_id: int = Depends(get_current_user_id),
) -> ApiResponse:
    project = _get_owned_project(db, project_id, user_id)
    delete_project(db, project)
    return ApiResponse(message="project deleted", data={"id": project_id})
