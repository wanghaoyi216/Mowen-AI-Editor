from fastapi import APIRouter

from app.api.confirmations import router as confirmations_router
from app.api.routes import (
    agent_stream,
    auth,
    books,
    chapter_scenes,
    chapters,
    character_events,
    characters,
    dashboard,
    entity_extraction,
    exports,
    graph,
    health,
    openrouter,
    plots,
    projects,
    story_arc,
    tasks,
    trends,
    workflows,
    worldbook,
)


api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(agent_stream.router, tags=["agent-stream"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(characters.router, prefix="/projects", tags=["characters"])
api_router.include_router(character_events.router, prefix="/projects", tags=["character-events"])
api_router.include_router(chapters.router, prefix="/projects", tags=["chapters"])
api_router.include_router(chapter_scenes.router, prefix="/projects", tags=["chapter-scenes"])
api_router.include_router(tasks.router, prefix="/projects", tags=["tasks"])
api_router.include_router(trends.router, prefix="/projects", tags=["trends"])
api_router.include_router(graph.router, prefix="/projects", tags=["graph"])
api_router.include_router(story_arc.router, prefix="/projects", tags=["story-arc"])
api_router.include_router(dashboard.router, prefix="/projects", tags=["dashboard"])
api_router.include_router(exports.router, prefix="/projects", tags=["exports"])
api_router.include_router(entity_extraction.router, prefix="/projects", tags=["entity-extraction"])
api_router.include_router(workflows.router, prefix="/projects", tags=["workflows"])
api_router.include_router(plots.router, prefix="/projects", tags=["plots"])
api_router.include_router(worldbook.router, prefix="/projects", tags=["worldbook"])
api_router.include_router(openrouter.router, prefix="/openrouter", tags=["openrouter"])
# 书籍：``/projects/{id}/books`` 路径 + ``/books/{id}`` 路径合并路由
api_router.include_router(books.project_books_router, tags=["books"])
api_router.include_router(books.book_router, tags=["books"])
api_router.include_router(confirmations_router, tags=["确认"])
