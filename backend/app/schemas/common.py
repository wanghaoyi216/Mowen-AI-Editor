from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    code: int = 200
    message: str = "ok"
    data: T | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
