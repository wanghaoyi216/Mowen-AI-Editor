from pydantic import BaseModel


class TaskStatusUpdate(BaseModel):
    status: str
    message: str | None = None
    current_step: str | None = None


class TaskControlRequest(BaseModel):
    action: str
    message: str | None = None


class TaskRuntimeState(BaseModel):
    task_id: int
    project_id: int
    status: str
    current_step: str | None = None
    message: str | None = None


class TaskStepStatusUpdate(BaseModel):
    step_no: int
    step_name: str
    status: str
    react_state: str
    message: str | None = None


class TaskStepRuntimeState(BaseModel):
    task_id: int
    project_id: int
    step_no: int
    step_name: str
    status: str
    react_state: str
    message: str | None = None


class TaskAlertRead(BaseModel):
    code: str
    severity: str
    message: str
    evidence: dict
