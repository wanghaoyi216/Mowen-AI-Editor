"""Async database session management"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.redis_client import get_redis_client


def _get_async_url() -> str:
    url = settings.database_url
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+asyncpg://")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    if url.startswith("sqlite"):
        return url.replace("sqlite", "sqlite+aiosqlite", 1)
    if url.startswith("mysql+pymysql://"):
        return url.replace("mysql+pymysql://", "mysql+aiomysql://")
    return url


async_engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    global async_engine, async_session_factory
    if async_session_factory is None:
        async_engine = create_async_engine(_get_async_url(), echo=False)
        async_session_factory = async_sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return async_session_factory


# 向后兼容：context_manager / 旧逻辑可能直接 ``from app.db.session import redis_client``
redis_client = get_redis_client()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_async_session_factory()() as session:
        yield session
