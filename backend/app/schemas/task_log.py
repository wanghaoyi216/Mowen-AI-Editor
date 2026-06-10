from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    step_no: int | None = None
    log_type: str
    message: str
    payload: str | None = None
    created_at: datetime


class TaskLogCreate(BaseModel):
    task_id: int
    step_no: int | None = None
    log_type: str
    message: str
    payload: str | None = None
