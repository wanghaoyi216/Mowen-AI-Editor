"""共享的"项目归属检查"依赖。"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db_session
from app.models.project import NovelProject
from app.services.project_service import get_project_for_user


def get_owned_project(
    project_id: int,
    db: Session = Depends(get_db_session),
    user_id: int = Depends(get_current_user_id),
) -> NovelProject:
    """FastAPI Depends：取一条属于当前用户的项目，否则 404。

    路由写法::

        @router.get("/{project_id}/chapters")
        def read_chapters(project: NovelProject = Depends(get_owned_project)):
            ...
    """
    project = get_project_for_user(db, project_id, user_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project
