from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.api.router import api_router
from app.core.config import settings
from app.db.base import create_db_and_tables
from app.db.migrations import run_startup_migrations
from app.services.task_persistence_service import TaskPersistenceManager

logger = logging.getLogger(__name__)


def create_application() -> FastAPI:
    app = FastAPI(
        title="Novel AI Editor API - AI 小说创作编辑器",
        description="AI 驱动的小说创作全链路自动化系统，支持热点探索、世界观构建、角色管理、剧情规划、章节写作、一致性检查和自动导出。用户只需设定超参数，AI 即可自动完成从热点搜索到章节导出的全流程。",
        version="0.2.0",
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=f"{settings.api_v1_prefix}/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        openapi_tags=[
            {"name": "项目", "description": "项目 CRUD 管理，创建、查看、更新、删除小说项目"},
            {"name": "角色", "description": "角色管理，创建和编辑小说中的角色档案、性格、背景等"},
            {"name": "章节", "description": "章节全流程管理，包括设计、草稿生成、一致性检查、修订和导出"},
            {"name": "任务", "description": "AI 任务管理，执行 ReAct 推理任务、控制任务运行状态、执行全链路创作"},
            {"name": "工作流", "description": "工作流编排，定义、注册和执行 AI 创作工作流"},
            {"name": "热点探索", "description": "热点搜索与趋势分析，发现热门题材并映射为创作资产"},
            {"name": "图数据库", "description": "图谱数据管理，查询和创建实体关系"},
            {"name": "导出", "description": "内容导出，支持单章 Markdown 导出和项目 ZIP 打包"},
            {"name": "剧情", "description": "剧情线管理，创建和编辑剧情线和故事事件"},
            {"name": "世界书", "description": "世界观管理，创建和编辑世界观条目"},
            {"name": "确认", "description": "阶段确认管理，Human-in-the-Loop 确认点控制"},
        ],
    )

    # CORS 白名单从环境变量读取（逗号分隔），默认包含 localhost 开发地址
    cors_origins_env = settings.cors_origins
    if cors_origins_env:
        allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
    else:
        allowed_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://0.0.0.0:5173",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request, exc: RequestValidationError) -> JSONResponse:
        field_errors = []
        for error in exc.errors():
            field_errors.append(
                {
                    "field": ".".join(str(part) for part in error.get("loc", [])),
                    "message": error.get("msg", ""),
                    "type": error.get("type", ""),
                }
            )
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "请求参数验证失败",
                "error_code": "ERR_VALIDATION",
                "data": None,
                "meta": {"field_errors": field_errors},
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "服务器内部错误，请稍后重试",
                "error_code": "ERR_INTERNAL",
                "data": None,
                "meta": {"detail": str(exc)},
            },
        )

    @app.on_event("startup")
    def on_startup() -> None:
        if settings.database_url.startswith("sqlite"):
            create_db_and_tables()
        # 启动迁移：补齐 owner_id / user_id 列、回填旧数据 owner_id=1、建索引
        # 幂等：多次运行结果一致；不会破坏已有数据。
        try:
            run_startup_migrations()
        except Exception as e:  # pragma: no cover
            logger.warning("Startup migrations failed (non-fatal): %s", e)

        # 清理 orphan task：上一轮进程崩了 / OOM / LLM 流式 hang 死，
        # daemon thread 已经不在 _active_threads 里但 DB 还显示 running 的 task
        # 全标为 paused，用户可走 /tasks/{id}/resume 续跑
        try:
            paused_ids = TaskPersistenceManager().mark_orphaned_tasks_as_paused()
            if paused_ids:
                logger.warning(
                    "Startup cleanup: marked %d orphan tasks as paused: %s",
                    len(paused_ids),
                    paused_ids,
                )
        except Exception as e:  # pragma: no cover - 启动期清理失败不影响服务
            logger.warning("Orphan task cleanup on startup failed (non-fatal): %s", e)

    @app.get("/", tags=["system"])
    def root() -> dict:
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "docs": "/api/v1/docs",
            "health": "/health",
        }

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_application()
