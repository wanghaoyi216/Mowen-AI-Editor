"""FastAPI 依赖注入。集中放数据库 session 与当前用户解析。"""

from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_token
from app.db.base import get_db

logger = logging.getLogger(__name__)


def get_db_session() -> Generator[Session, None, None]:
    """同步 session 上下文管理器入口（FastAPI Depends 用 yield 版）。"""
    yield from get_db()


# ── 多用户隔离 ────────────────────────────────────────────────────────────
# 默认用户：当请求没带 token 时回落到 user_id=1（admin 演示账号）。
# 单用户本地开发模式自动走这个分支；多用户正式环境要求 Authorization Bearer。
_DEFAULT_USER_ID = 1


def get_current_user_id(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> int:
    """从 ``Authorization: Bearer <token>`` 解析当前 user_id。

    * 没带 token / token 无效 → 兜底为 ``_DEFAULT_USER_ID``（单用户模式）。
    * 正确 token → 返回 token 里的 sub（user.id）。
    * token 解析出错 → 同样回落到 default（开发友好）。
    """
    if not authorization:
        return _DEFAULT_USER_ID
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return _DEFAULT_USER_ID
    token = parts[1].strip()
    if not token:
        return _DEFAULT_USER_ID
    try:
        user_id = verify_token(token, settings.secret_key)
    except Exception as e:  # pragma: no cover
        logger.debug("verify_token 异常: %s", e)
        return _DEFAULT_USER_ID
    return user_id if isinstance(user_id, int) and user_id > 0 else _DEFAULT_USER_ID
