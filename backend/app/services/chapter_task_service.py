from sqlalchemy.orm import Session

from app.schemas.ai_task import AITaskCreate
from app.schemas.chapter_version import ChapterRevisionRequest
from app.schemas.entity_extraction import EntityExtractionRequest
from app.schemas.task_runtime import TaskStatusUpdate, TaskStepStatusUpdate
from app.services.chapter_ai_service import build_chapter_plan, generate_chapter_draft, revise_chapter_draft
from app.services.entity_extraction_service import extract_entities_from_text
from app.services.task_runtime_service import set_task_runtime_state, set_task_step_runtime_state
from app.services.task_service import create_task, create_task_step


def execute_chapter_design_task(
    db: Session,
    project_id: int,
    chapter_id: int,
    plot_line_id: int | None = None,
    guidance: str | None = None,
) -> dict:
    task = create_task(
        db,
        project_id,
        AITaskCreate(
            chapter_id=chapter_id,
            plot_line_id=plot_line_id,
            task_type="chapter_design",
            module_type="chapter_planning",
            title=f"Chapter {chapter_id} design task",
            input_payload=guidance,
            plan_text="Collect Assets -> Design Brief -> Beat Sheet -> Persist",
            status="running",
        ),
    )
    step_specs = [
        (1, "Collect Assets", "asset_collection", "observe", "Collect project writing assets"),
        (2, "Design Brief", "design", "reason", "Create chapter design brief"),
        (3, "Beat Sheet", "planning", "plan", "Generate scene beats"),
        (4, "Persist", "save", "act", "Persist chapter plan"),
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
                status="completed" if step_no < 4 else "running",
                input_payload=payload,
            )
        )

    plan = build_chapter_plan(
        db,
        project_id=project_id,
        chapter_id=chapter_id,
        plot_line_id=plot_line_id,
        guidance=guidance,
    )

    for step in steps:
        set_task_step_runtime_state(
            project_id,
            task.id,
            TaskStepStatusUpdate(
                step_no=step.step_no,
                step_name=step.step_name,
                status="completed",
                react_state=step.react_state,
                message=f"{step.step_name} completed",
            ),
        )

    set_task_runtime_state(
        project_id,
        task.id,
        TaskStatusUpdate(status="completed", current_step="finished", message="Chapter design completed"),
    )
    return {"task": task, "steps": steps, "plan": plan}


def execute_chapter_generate_task(
    db: Session,
    project_id: int,
    chapter_id: int,
    style_hint: str | None = None,
    word_target: int | None = None,
) -> dict:
    task = create_task(
        db,
        project_id,
        AITaskCreate(
            chapter_id=chapter_id,
            task_type="chapter_generation",
            module_type="chapter_writing",
            title=f"Chapter {chapter_id} draft task",
            input_payload=style_hint,
            plan_text="Load Plan -> Compose Draft -> Persist Draft",
            status="running",
        ),
    )
    step_specs = [
        (1, "Load Plan", "loading", "observe", "Load chapter plan and assets"),
        (2, "Compose Draft", "generation", "act", "Compose the full chapter draft"),
        (3, "Persist Draft", "save", "extract", "Persist chapter draft"),
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

    chapter = generate_chapter_draft(
        db,
        project_id=project_id,
        chapter_id=chapter_id,
        style_hint=style_hint,
        word_target=word_target,
    )

    for step in steps:
        set_task_step_runtime_state(
            project_id,
            task.id,
            TaskStepStatusUpdate(
                step_no=step.step_no,
                step_name=step.step_name,
                status="completed",
                react_state=step.react_state,
                message=f"{step.step_name} completed",
            ),
        )

    set_task_runtime_state(
        project_id,
        task.id,
        TaskStatusUpdate(status="completed", current_step="finished", message="Chapter draft completed"),
    )
    return {"task": task, "steps": steps, "chapter": chapter}


def execute_chapter_revision_task(
    db: Session,
    project_id: int,
    chapter_id: int,
    payload: ChapterRevisionRequest,
) -> dict:
    task = create_task(
        db,
        project_id,
        AITaskCreate(
            chapter_id=chapter_id,
            task_type="chapter_revision",
            module_type="chapter_rewriting",
            title=f"Chapter {chapter_id} revision task",
            input_payload=payload.revision_focus or payload.style_hint,
            plan_text="Check Draft -> Produce Revision Guidance -> Rewrite Draft -> Persist Version -> Extract Entities",
            status="running",
        ),
    )
    step_specs = [
        (1, "Check Draft", "consistency_check", "observe", "Review chapter consistency"),
        (2, "Produce Revision Guidance", "reasoning", "reason", "Extract actionable rewrite direction"),
        (3, "Rewrite Draft", "rewrite", "act", "Rewrite the draft using the consistency report"),
        (4, "Persist Version", "save", "extract", "Persist revised chapter version"),
        (5, "Extract Entities", "entity_extraction", "extract", "Analyze final content before graph store"),
    ]
    steps = []
    for step_no, step_name, step_type, react_state, input_payload in step_specs:
        steps.append(
            create_task_step(
                db,
                project_id,
                task.id,
                step_no=step_no,
                step_name=step_name,
                step_type=step_type,
                react_state=react_state,
                status="completed" if step_no < 4 else "running",
                input_payload=input_payload,
            )
        )

    result = revise_chapter_draft(
        db,
        project_id=project_id,
        chapter_id=chapter_id,
        revision_focus=payload.revision_focus,
        style_hint=payload.style_hint,
        word_target=payload.word_target,
    )
    extraction_summary = extract_entities_from_text(
        db,
        project_id,
        EntityExtractionRequest(
            text=result["chapter"].final_content or result["chapter"].draft_content or "",
            source_type="chapter_final_content",
            source_ref=f"chapter-{chapter_id}",
            task_id=task.id,
        ),
    )

    for step in steps:
        message = f"{step.step_name} completed"
        if step.step_name == "Check Draft":
            message = result["consistency_report"][:240]
        if step.step_name == "Rewrite Draft":
            message = f"rewrite model: {result['rewrite_model']}"
        if step.step_name == "Extract Entities":
            message = (
                f"graph mutations: entities +{extraction_summary['added_entities']} / "
                f"relationships +{extraction_summary['added_relationships']}"
            )
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
        TaskStatusUpdate(status="completed", current_step="finished", message="Chapter revision completed"),
    )
    return {
        "task": task,
        "steps": steps,
        "chapter": result["chapter"],
        "version": result["version"],
        "consistency_report": result["consistency_report"],
        "consistency_model": result["consistency_model"],
        "rewrite_model": result["rewrite_model"],
        "entity_extraction": extraction_summary,
    }
