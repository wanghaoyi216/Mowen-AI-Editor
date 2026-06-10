from sqlalchemy.orm import Session

from app.schemas.ai_task import AITaskCreate
from app.schemas.task_runtime import TaskStatusUpdate, TaskStepStatusUpdate
from app.services.chapter_consistency_service import run_chapter_consistency_check
from app.services.task_runtime_service import set_task_runtime_state, set_task_step_runtime_state
from app.services.task_service import create_task, create_task_step


def execute_chapter_consistency_task(db: Session, project_id: int, chapter_id: int) -> dict:
    task = create_task(
        db,
        project_id,
        AITaskCreate(
            chapter_id=chapter_id,
            task_type="chapter_consistency_check",
            module_type="chapter_quality",
            title=f"Chapter {chapter_id} consistency check",
            plan_text="Load Assets -> Compare Draft -> Report Issues",
            status="running",
        ),
    )
    step_specs = [
        (1, "Load Assets", "loading", "observe", "Load chapter draft, plan, characters, plot lines, worldbook"),
        (2, "Compare Draft", "analysis", "reason", "Compare draft against story constraints"),
        (3, "Report Issues", "report", "extract", "Produce consistency report"),
    ]
    steps = []
    for step_no, step_name, step_type, react_state, payload in step_specs:
        steps.append(
            create_task_step(
                db,
                project_id,
                task.id,
                step_no=step_no,
                step_name=step_name,
                step_type=step_type,
                react_state=react_state,
                status="completed" if step_no < 3 else "running",
                input_payload=payload,
            )
        )

    result = run_chapter_consistency_check(db, project_id, chapter_id)

    for step in steps:
        message = f"{step.step_name} completed"
        if step.step_name == "Report Issues":
            message = result["report"][:240]
        set_task_step_runtime_state(
            project_id,
            task.id,
            TaskStepStatusUpdate(
                step_no=step.step_no,
                step_name=step.step_name,
                status="completed",
                react_state=step.react_state,
                message=message,
            ),
        )

    set_task_runtime_state(
        project_id,
        task.id,
        TaskStatusUpdate(status="completed", current_step="finished", message="Chapter consistency check completed"),
    )
    return {"task": task, "steps": steps, "report": result["report"], "model": result["model"]}
