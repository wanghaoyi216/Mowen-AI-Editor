from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


def _to_sync_url(url: str) -> str:
    """把 async 驱动 URL 转成 sync 驱动 URL。

    规则：
      * ``mysql+aiomysql://``  →  ``mysql+pymysql://``
      * ``postgresql+asyncpg://``  →  ``postgresql+psycopg2://``
    其他驱动原样返回。
    """
    if not url:
        return url
    replacements = (
        ("mysql+aiomysql://", "mysql+pymysql://"),
        ("postgresql+asyncpg://", "postgresql+psycopg2://"),
    )
    for old, new in replacements:
        if url.startswith(old):
            return new + url[len(old):]
    return url


# 同步 engine：给 alembic 迁移和路由 Session 使用
sync_url = _to_sync_url(settings.database_url)
# MySQL 必须显式指定 utf8mb4，否则默认 latin1 会导致中文/Emoji 截断与乱码
# 注意：SQLAlchemy dialect 是 ``mysql+<driver>``（如 mysql+pymysql），startswith("mysql")
# 会同时命中 ``mysql://``、``mysql+pymysql://``、``mysql+aiomysql://``，但本函数已把 aiomysql
# 转成 pymysql，所以同步 URL 一定形如 ``mysql+pymysql://`` 或 ``mysql://``。
connect_args: dict = {"check_same_thread": False} if sync_url.startswith("sqlite") else {}
if sync_url.startswith("mysql") and "charset=" not in sync_url:
    # 用 querystring 形式注入 charset=utf8mb4，避免修改 env
    sep = "&" if "?" in sync_url else "?"
    sync_url = f"{sync_url}{sep}charset=utf8mb4"
engine = create_engine(sync_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def create_db_and_tables() -> None:
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
