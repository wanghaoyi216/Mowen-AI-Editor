from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AITaskBase(BaseModel):
    chapter_id: int | None = None
    plot_line_id: int | None = None
    task_type: str
    module_type: str
    title: str
    input_payload: str | None = None
    plan_text: str | None = None
    reasoning_trace: str | None = None
    tool_trace: str | None = None
    output_payload: str | None = None
    workflow_execution_id: str | None = None
    status: str = "pending"
    error_message: str | None = None


class AITaskCreate(AITaskBase):
    pass


class AITaskRead(AITaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class TaskStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    step_no: int
    step_name: str
    step_type: str
    react_state: str
    input_payload: str | None = None
    output_payload: str | None = None
    tool_name: str | None = None
    status: str
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class TaskStepCreate(BaseModel):
    step_no: int
    step_name: str
    step_type: str
    react_state: str
    status: str = "pending"
    tool_name: str | None = None
    input_payload: str | None = None
