"""阶段确认相关 Pydantic 模型"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConfirmationResponse(BaseModel):
    task_id: int = Field(description="任务 ID")
    workflow_id: str = Field(description="工作流 ID")
    point_id: str = Field(description="确认点 ID")
    message: str = Field(description="确认提示信息")
    summary: dict[str, Any] | None = Field(default=None, description="阶段成果摘要")
    created_at: datetime = Field(description="创建时间")


class ApproveConfirmationRequest(BaseModel):
    human_input: str | None = Field(default=None, description="人类输入的补充建议")


class SkipConfirmationRequest(BaseModel):
    pass


class SetModeRequest(BaseModel):
    mode: str = Field(description="运行模式：auto=全自动，confirm=多阶段确认")


class ChainExecutionStatus(BaseModel):
    task_id: int = Field(description="任务 ID")
    mode: str = Field(description="当前运行模式")
    current_workflow_id: str | None = Field(default=None, description="当前执行的工作流 ID")
    current_confirmation_point: str | None = Field(default=None, description="当前确认点")
    status: str = Field(description="任务状态")
    human_input: str | None = Field(default=None, description="人类输入建议")
