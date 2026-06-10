"""用户认证相关 schema"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    """用户注册请求"""

    username: str = Field(min_length=3, max_length=64, description="用户名（3-64字符）")
    password: str = Field(min_length=6, max_length=64, description="密码（6-64字符）")
    email: Optional[EmailStr] = Field(default=None, description="可选邮箱")
    display_name: Optional[str] = Field(default=None, max_length=120, description="显示名")

    @field_validator("username")
    @classmethod
    def _validate_username(cls, v: str) -> str:
        # 必须是字母/数字/中文/下划线/连字符
        import re

        if not re.match(r"^[A-Za-z0-9_\-\u4e00-\u9fa5]+$", v):
            raise ValueError("用户名只能包含字母、数字、中文、下划线、连字符")
        return v


class UserLoginRequest(BaseModel):
    """用户登录请求"""

    username: str = Field(min_length=3, max_length=64, description="用户名")
    password: str = Field(min_length=6, max_length=64, description="密码")


class UserRead(BaseModel):
    """用户读取（不含密码）"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime


class AuthTokenResponse(BaseModel):
    """登录成功响应"""

    user: UserRead
    token: str = Field(description="访问令牌（Bearer Token）")
    expires_at: datetime = Field(description="令牌过期时间")
