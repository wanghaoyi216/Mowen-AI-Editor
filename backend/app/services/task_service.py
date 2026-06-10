from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.ai_task import AITask, TaskLog, TaskStep
from app.models.trend_exploration import TrendExploration
from app.schemas.ai_task import AITaskCreate
from app.schemas.task_runtime import TaskStatusUpdate, TaskStepStatusUpdate
from app.services.task_runtime_service import set_task_runtime_state, set_task_step_runtime_state


def list_tasks(db: Session, project_id: int, chapter_id: int | None = None) -> list[AITask]:
    query = select(AITask).where(AITask.project_id == project_id)
    if chapter_id is not None:
        query = query.where(AITask.chapter_id == chapter_id)
    return list(db.scalars(query.order_by(AITask.created_at.desc())))


def get_task(db: Session, project_id: int, task_id: int) -> AITask | None:
    task = db.get(AITask, task_id)
    if task is None or task.project_id != project_id:
        return None
    return task


def get_task_by_workflow_execution_id(
    db: Session,
    project_id: int,
    workflow_execution_id: str,
) -> AITask | None:
    return db.scalar(
        select(AITask).where(
            AITask.project_id == project_id,
            AITask.workflow_execution_id == workflow_execution_id,
        )
    )


def create_task(db: Session, project_id: int, payload: AITaskCreate) -> AITask:
    task = AITask(project_id=project_id, **payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    set_task_runtime_state(
        project_id,
        task.id,
        TaskStatusUpdate(
            status=task.status,
            message="Task created",
            current_step="created",
        ),
    )
    return task


def list_task_steps(db: Session, task_id: int) -> list[TaskStep]:
    return list(db.scalars(select(TaskStep).where(TaskStep.task_id == task_id).order_by(TaskStep.step_no.asc())))


def create_task_step(
    db: Session,
    project_id: int,
    task_id: int,
    step_no: int,
    step_name: str,
    step_type: str,
    react_state: str,
    status: str = "pending",
    tool_name: str | None = None,
    input_payload: str | None = None,
) -> TaskStep:
    step = TaskStep(
        task_id=task_id,
        step_no=step_no,
        step_name=step_name,
        step_type=step_type,
        react_state=react_state,
        status=status,
        tool_name=tool_name,
        input_payload=input_payload,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    set_task_step_runtime_state(
        project_id,
        task_id,
        TaskStepStatusUpdate(
            step_no=step.step_no,
            step_name=step.step_name,
            status=step.status,
            react_state=step.react_state,
            message="Task step created",
        ),
    )
    return step


def delete_task(db: Session, project_id: int, task_id: int) -> bool:
    task = get_task(db, project_id, task_id)
    if task is None:
        return False

    stmt = delete(TaskStep).where(TaskStep.task_id == task_id)
    db.execute(stmt)

    log_stmt = delete(TaskLog).where(TaskLog.task_id == task_id)
    db.execute(log_stmt)

    # 级联清空该项目下的全部趋势调研记录。
    # 右侧"热点探索"tab 100% 从 trend_explorations 表聚合（探索次数、累计/唯一标签、
    # 高频标签 Top 12、近 7 日频次、题材调研、AI 下一步建议），不删这条数据 tab 就一直显示。
    trend_stmt = delete(TrendExploration).where(TrendExploration.project_id == project_id)
    db.execute(trend_stmt)

    db.delete(task)
    db.commit()
    return True


def create_task_log(
    db: Session,
    task_id: int,
    step_no: int | None,
    log_type: str,
    message: str,
    payload: str | None = None,
) -> TaskLog:
    log = TaskLog(task_id=task_id, step_no=step_no, log_type=log_type, message=message, payload=payload)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_task_logs(db: Session, task_id: int, limit: int = 100) -> list[TaskLog]:
    return list(
        db.scalars(
            select(TaskLog)
            .where(TaskLog.task_id == task_id)
            .order_by(TaskLog.created_at.asc())
            .limit(limit)
        )
    )
