"""Project service ── 多用户隔离版。"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.ai_task import AITask, TaskStep
from app.models.book import Book
from app.models.character import Character
from app.models.character_event_participation import CharacterEventParticipation
from app.models.character_relationship import CharacterRelationship
from app.models.chapter import Chapter
from app.models.chapter_plan import ChapterPlan
from app.models.chapter_version import ChapterVersion
from app.models.plot_line import PlotLine
from app.models.project import NovelProject
from app.models.story_event import StoryEvent
from app.models.trend_exploration import TrendExploration
from app.models.worldbook_entry import WorldbookEntry
from app.schemas.project import ProjectCreate, ProjectUpdate


# ── 多用户隔离查询 ───────────────────────────────────────────────────────────
def list_projects_for_user(db: Session, user_id: int) -> list[NovelProject]:
    """列出当前用户的项目。兼容老数据：owner_id 缺失时回退到 user_id 字段。"""
    stmt = (
        select(NovelProject)
        .where(
            or_(
                NovelProject.owner_id == user_id,
                NovelProject.user_id == user_id,  # 历史/兼容字段
            )
        )
        .order_by(NovelProject.updated_at.desc())
    )
    return list(db.scalars(stmt))


def get_project_for_user(db: Session, project_id: int, user_id: int) -> NovelProject | None:
    """取一条属于 user_id 的项目。"""
    return db.scalar(
        select(NovelProject).where(
            NovelProject.id == project_id,
            or_(
                NovelProject.owner_id == user_id,
                NovelProject.user_id == user_id,
            ),
        )
    )


# ── 兼容旧调用点（无 user_id）─────────────────────────────────────────────
def list_projects(db: Session) -> list[NovelProject]:
    """⚠ 仅供管理后台 / 测试使用。生产路由请走 ``list_projects_for_user``。"""
    return list(db.scalars(select(NovelProject).order_by(NovelProject.updated_at.desc())))


def get_project(db: Session, project_id: int) -> NovelProject | None:
    """⚠ 不带用户过滤。生产路由请走 ``get_project_for_user``。"""
    return db.get(NovelProject, project_id)


# ── 写操作 ────────────────────────────────────────────────────────────────
def create_project(db: Session, payload: ProjectCreate, owner_id: int = 1) -> NovelProject:
    """创建项目。``owner_id`` 必传，调用方应为路由层解析的 current user_id。"""
    data = payload.model_dump()
    project = NovelProject(**data, owner_id=owner_id, user_id=owner_id)
    db.add(project)
    db.flush()  # 取到 project.id
    # 自动创建默认 book
    default_book = Book(
        project_id=project.id,
        name=f"{project.name} - 默认书",
        order_index=1,
    )
    db.add(default_book)
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project: NovelProject, payload: ProjectUpdate) -> NovelProject:
    for field, value in payload.model_dump(exclude_unset=True).items():
        # 防止客户端篡改所有者
        if field in ("owner_id", "user_id"):
            continue
        setattr(project, field, value)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project: NovelProject) -> None:
    project_id = project.id
    task_ids = list(db.scalars(select(AITask.id).where(AITask.project_id == project_id)))
    if task_ids:
        db.query(TaskStep).filter(TaskStep.task_id.in_(task_ids)).delete(synchronize_session=False)

    for model in (
        ChapterVersion,
        ChapterPlan,
        CharacterEventParticipation,
        CharacterRelationship,
        StoryEvent,
        Chapter,
        AITask,
        TrendExploration,
        WorldbookEntry,
        PlotLine,
        Character,
        Book,
    ):
        db.query(model).filter(model.project_id == project_id).delete(synchronize_session=False)

    db.delete(project)
    db.commit()
