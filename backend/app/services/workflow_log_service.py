from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_task import AITask, TaskLog, TaskStep


WORKFLOW_LOG_ROOT = Path(__file__).resolve().parents[3] / "cache-memory" / "workflow_logs"

WORKFLOW_LOG_FOLDERS = {
    "wf-01": "wf-01_trend_inspiration",
    "wf-02": "wf-02_worldbuilding",
    "wf-03": "wf-03_outline_planning",
    "wf-04": "wf-04_chapter_writing",
    "wf-05": "wf-05_entity_extraction",
}


def _format_value(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def write_workflow_execution_log(db: Session, task: AITask) -> dict[str, str]:
    folder_name = WORKFLOW_LOG_FOLDERS.get(task.task_type.lower(), task.task_type.lower())
    folder = WORKFLOW_LOG_ROOT / folder_name
    folder.mkdir(parents=True, exist_ok=True)

    steps = list(db.scalars(select(TaskStep).where(TaskStep.task_id == task.id).order_by(TaskStep.step_no.asc())))
    logs = list(db.scalars(select(TaskLog).where(TaskLog.task_id == task.id).order_by(TaskLog.created_at.asc())))

    plan_lines = [
        f"# {task.task_type.upper()} plan",
        "",
        f"- task_id: {task.id}",
        f"- title: {task.title}",
        f"- status: {task.status}",
        f"- workflow_execution_id: {_format_value(task.workflow_execution_id)}",
        "",
        "## Plan",
        "",
        task.plan_text or "No plan text.",
        "",
    ]
    trace_lines = [
        f"# {task.task_type.upper()} trace",
        "",
        f"- task_id: {task.id}",
        f"- title: {task.title}",
        f"- status: {task.status}",
        f"- started_at: {_format_value(task.started_at)}",
        f"- finished_at: {_format_value(task.finished_at)}",
        "",
        "## Steps",
        "",
    ]
    if steps:
        for step in steps:
            trace_lines.append(f"- {step.step_no}. {step.step_name} / {step.step_type} / {step.react_state} / {step.status}")
    else:
        trace_lines.append("No steps recorded.")

    trace_lines.extend(["", "## Task Logs", ""])
    if logs:
        for log in logs:
            trace_lines.append(f"- {log.created_at}: {log.log_type} - {log.message}")
    else:
        trace_lines.append("No task logs recorded.")

    if task.reasoning_trace:
        trace_lines.extend(["", "## Reasoning Trace", "", "```json", task.reasoning_trace, "```"])
    if task.tool_trace:
        trace_lines.extend(["", "## Tool Trace", "", "```json", task.tool_trace, "```"])
    if task.output_payload:
        trace_lines.extend(["", "## Output", "", "```json", task.output_payload, "```"])

    plan_path = folder / "plan.md"
    trace_path = folder / "trace.md"
    plan_path.write_text("\n".join(plan_lines), encoding="utf-8")
    trace_path.write_text("\n".join(trace_lines), encoding="utf-8")
    return {"plan_path": str(plan_path), "trace_path": str(trace_path)}
