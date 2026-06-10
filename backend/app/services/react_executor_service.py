from sqlalchemy.orm import Session

from app.schemas.ai_task import AITaskCreate
from app.schemas.task_runtime import TaskStatusUpdate, TaskStepStatusUpdate
from app.services.ai_workflow_graph_service import run_react_workflow
from app.services.openrouter_service import generate_with_openrouter
from app.services.trend_service import execute_trend_exploration
from app.services.task_runtime_service import set_task_runtime_state, set_task_step_runtime_state
from app.services.task_service import create_task, create_task_step, list_task_steps


def execute_minimal_react_task(
    db: Session,
    project_id: int,
    title: str,
    module_type: str,
    objective: str,
    chapter_id: int | None = None,
    plot_line_id: int | None = None,
) -> dict:
    task = create_task(
        db,
        project_id,
        AITaskCreate(
            chapter_id=chapter_id,
            plot_line_id=plot_line_id,
            task_type="react_execution",
            module_type=module_type,
            title=title,
            input_payload=objective,
            plan_text="Plan -> Reason -> Act -> Observe -> Extract",
            status="running",
        ),
    )

    state = run_react_workflow(
        db,
        project_id,
        task,
        objective,
        project_context={
            "module_type": module_type,
            "chapter_id": chapter_id,
            "plot_line_id": plot_line_id,
        },
        max_steps=3,
    )
    steps = list_task_steps(db, task.id)

    return {"task": task, "steps": steps, "state": state}


def execute_trend_react_task(
    db: Session,
    project_id: int,
    title: str,
    query_text: str,
    source_scope: str = "web",
) -> dict:
    task = create_task(
        db,
        project_id,
        AITaskCreate(
            task_type="trend_react_execution",
            module_type="trend_exploration",
            title=title,
            input_payload=query_text,
            plan_text="Plan -> Search -> Scrape -> Extract -> Suggest",
            status="running",
        ),
    )

    step_specs = [
        (1, "Plan", "planning", "plan", "Define trend exploration objective"),
        (2, "Search", "search", "act", "Search current web results"),
        (3, "Scrape", "scrape", "observe", "Scrape high-value pages"),
        (4, "Extract", "extraction", "extract", "Extract topics and tags"),
        (5, "Suggest", "synthesis", "reason", "Generate direction suggestions"),
    ]

    steps = []
    for step_no, step_name, step_type, react_state, payload in step_specs:
        step = create_task_step(
            db,
            project_id,
            task.id,
            step_no=step_no,
            step_name=step_name,
            step_type=step_type,
            react_state=react_state,
            status="completed" if step_no < 5 else "running",
            input_payload=payload,
        )
        steps.append(step)

    set_task_runtime_state(
        project_id,
        task.id,
        TaskStatusUpdate(status="running", current_step="search", message="Trend ReAct execution started"),
    )

    trend = execute_trend_exploration(
        db,
        project_id=project_id,
        title=title,
        query_text=query_text,
        source_scope=source_scope,
    )

    try:
        llm_result = generate_with_openrouter(
            system_prompt="You are an AI novel trend analyst. Extract useful writing directions from search results.",
            user_prompt=f"Analyze this trend query and propose 3 strong directions for a novel project: {query_text}",
            preferred_keywords=["qwen", "mistral", "llama", "gemini"],
        )
        llm_message = llm_result["completion"]["choices"][0]["message"]["content"]
    except Exception:
        llm_message = "OpenRouter generation unavailable; trend search result still stored."

    for step in steps:
        final_status = "completed"
        message = f"{step.step_name} completed"
        if step.step_name == "Suggest":
            message = llm_message[:240]
        set_task_step_runtime_state(
            project_id,
            task.id,
            TaskStepStatusUpdate(
                step_no=step.step_no,
                step_name=step.step_name,
                status=final_status,
                react_state=step.react_state,
                message=message,
            ),
        )

    set_task_runtime_state(
        project_id,
        task.id,
        TaskStatusUpdate(status="completed", current_step="finished", message="Trend ReAct execution completed"),
    )

    return {"task": task, "steps": steps, "trend": trend, "llm_message": llm_message}
