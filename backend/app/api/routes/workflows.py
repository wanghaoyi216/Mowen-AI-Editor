from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.ai_task import AITaskRead, TaskStepRead
from app.schemas.common import ApiResponse
from app.schemas.workflow_orchestration import WorkflowDefinitionRead, WorkflowExecuteRequest
from app.services.workflow_registry_service import (
    execute_registered_workflow,
    get_workflow_definition,
    list_workflow_definitions,
)


router = APIRouter()


@router.get("/{project_id}/workflows", response_model=ApiResponse)
def read_workflows(project_id: int) -> ApiResponse:
    _ = project_id
    return ApiResponse(data=[WorkflowDefinitionRead.model_validate(item) for item in list_workflow_definitions()])


@router.get("/{project_id}/workflows/{workflow_id}", response_model=ApiResponse)
def read_workflow(project_id: int, workflow_id: str) -> ApiResponse:
    _ = project_id
    item = get_workflow_definition(workflow_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return ApiResponse(data=WorkflowDefinitionRead.model_validate(item))


@router.post("/{project_id}/workflows/{workflow_id}/execute", response_model=ApiResponse)
def execute_workflow_endpoint(
    project_id: int,
    workflow_id: str,
    payload: WorkflowExecuteRequest,
    db: Session = Depends(get_db_session),
) -> ApiResponse:
    try:
        result = execute_registered_workflow(db, project_id, workflow_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ApiResponse(
        message="workflow executed",
        data={
            "workflow": WorkflowDefinitionRead.model_validate(result["definition"]),
            "task": AITaskRead.model_validate(result["task"]),
            "steps": [TaskStepRead.model_validate(step) for step in result["steps"]],
            "idempotent_replay": result["idempotent_replay"],
        },
    )
