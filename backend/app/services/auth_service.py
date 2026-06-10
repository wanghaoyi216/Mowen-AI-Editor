"""用户认证服务（注册/登录/查询）"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, issue_token, verify_password
from app.core.config import settings
from app.models.user import User
from app.schemas.user import UserLoginRequest, UserRegisterRequest


# 统一 token 密钥：与 deps.get_current_user_id / verify_token 保持一致。
# 必须**懒求值**（每次调用读 settings），不能用模块级常量！
# 模块加载时 settings.secret_key 可能还是 ""，main.py 在模块加载后才
# 把它随机化为 dev 临时值；用模块级常量会捕获到 ""，导致签发的 token
# 永远用空字符串签名，验证（用随机值）永远失败，多用户隔离形同虚设。
def _get_token_secret() -> str:
    return (
        settings.secret_key
        or getattr(settings, "nvidia_api_key", None)
        or "mowen-novel-ai-editor-secret"
    )


def register_user(db: Session, payload: UserRegisterRequest) -> User:
    """注册新用户。用户名已存在时抛 ValueError。"""
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing is not None:
        raise ValueError("用户名已存在")

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name or payload.username,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, payload: UserLoginRequest) -> Optional[User]:
    """校验用户名+密码。成功返回 User，失败返回 None。"""
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not user.is_active:
        return None
    if not verify_password(payload.password, user.password_hash):
        return None

    user.last_login_at = datetime.now(tz=timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def issue_user_token(user: User) -> tuple[str, datetime]:
    """签发用户 token。"""
    token, exp = issue_token(user.id, _get_token_secret())
    return token, datetime.fromtimestamp(exp, tz=timezone.utc)


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.scalar(select(User).where(User.id == user_id))


def authenticate_request_token(db: Session, token: str) -> Optional[User]:
    """根据 token 解析用户（中间件/依赖用）。"""
    from app.core.security import verify_token

    user_id = verify_token(token, _get_token_secret())
    if user_id is None:
        return None
    return get_user_by_id(db, user_id)
