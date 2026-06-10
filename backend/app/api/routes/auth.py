"""用户认证路由（注册/登录/获取当前用户）"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.common import ApiResponse
from app.schemas.user import AuthTokenResponse, UserLoginRequest, UserRead, UserRegisterRequest
from app.services.auth_service import (
    authenticate,
    authenticate_request_token,
    get_user_by_id,
    issue_user_token,
    register_user,
)


router = APIRouter()


@router.post("/register", response_model=ApiResponse)
def register_endpoint(
    payload: UserRegisterRequest,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    """注册新用户。"""
    try:
        user = register_user(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    token, expires_at = issue_user_token(user)
    return ApiResponse(
        message="注册成功",
        data=AuthTokenResponse(
            user=UserRead.model_validate(user),
            token=token,
            expires_at=expires_at,
        ),
    )


@router.post("/login", response_model=ApiResponse)
def login_endpoint(
    payload: UserLoginRequest,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    """登录获取 token。"""
    user = authenticate(db, payload)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token, expires_at = issue_user_token(user)
    return ApiResponse(
        message="登录成功",
        data=AuthTokenResponse(
            user=UserRead.model_validate(user),
            token=token,
            expires_at=expires_at,
        ),
    )


@router.get("/me", response_model=ApiResponse)
def me_endpoint(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    """根据 Bearer Token 返回当前登录用户。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供登录凭证")
    token = authorization.split(" ", 1)[1].strip()
    user = authenticate_request_token(db, token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录凭证无效或已过期")
    return ApiResponse(
        message="ok",
        data=UserRead.model_validate(user),
    )
