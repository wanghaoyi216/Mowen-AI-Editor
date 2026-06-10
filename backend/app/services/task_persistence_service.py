"""Task persistence and auto-recovery service.

This module provides checkpoint-based persistence for long-running AI tasks so
that they can be resumed after crashes, restarts or network failures. The
:class:`TaskPersistenceManager` records incremental progress (completed
chapters, accumulated context, failure history) to the database and exposes
utilities to identify and recover orphaned tasks that no longer have an
active worker thread.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.ai_task import AITask
from app.models.task_checkpoint import TaskCheckpoint


logger = logging.getLogger(__name__)


@dataclass
class CheckpointData:
    """Structured payload persisted alongside a task checkpoint."""

    task_id: int
    current_phase: str
    completed_chapters: list[int] = field(default_factory=list)
    total_chapters: int = 0
    last_chapter_no: int | None = None
    accumulated_context: dict[str, Any] = field(default_factory=dict)
    failure_history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "current_phase": self.current_phase,
            "completed_chapters": list(self.completed_chapters),
            "total_chapters": self.total_chapters,
            "last_chapter_no": self.last_chapter_no,
            "accumulated_context": dict(self.accumulated_context),
            "failure_history": list(self.failure_history),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CheckpointData":
        return cls(
            task_id=int(payload.get("task_id", 0)),
            current_phase=str(payload.get("current_phase", "pending")),
            completed_chapters=list(payload.get("completed_chapters", []) or []),
            total_chapters=int(payload.get("total_chapters", 0) or 0),
            last_chapter_no=(
                int(payload["last_chapter_no"])
                if payload.get("last_chapter_no") is not None
                else None
            ),
            accumulated_context=dict(payload.get("accumulated_context", {}) or {}),
            failure_history=list(payload.get("failure_history", []) or []),
        )


class TaskPersistenceManager:
    """Manage checkpoint persistence and recovery for AI tasks.

    The manager keeps an in-memory registry of active worker threads so it
    can distinguish a genuinely running task from one that was left in the
    ``running`` state by a previous worker process that has since died.
    """

    _active_threads: dict[int, threading.Thread] = {}
    _registry_lock = threading.Lock()

    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Thread registry helpers
    # ------------------------------------------------------------------
    @classmethod
    def register_active_thread(cls, task_id: int, thread: threading.Thread) -> None:
        with cls._registry_lock:
            cls._active_threads[task_id] = thread

    @classmethod
    def unregister_active_thread(cls, task_id: int) -> None:
        with cls._registry_lock:
            cls._active_threads.pop(task_id, None)

    @classmethod
    def is_thread_active(cls, task_id: int) -> bool:
        with cls._registry_lock:
            thread = cls._active_threads.get(task_id)
            if thread is None:
                return False
            return thread.is_alive()

    # ------------------------------------------------------------------
    # Session helper
    # ------------------------------------------------------------------
    def _session_scope(self) -> tuple[Session, bool]:
        if self.db is not None:
            return self.db, False
        session = SessionLocal()
        return session, True

    @staticmethod
    def _commit(session: Session, owned: bool) -> None:
        if owned:
            session.commit()

    @staticmethod
    def _close(session: Session, owned: bool) -> None:
        if owned:
            session.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def save_task_checkpoint(
        self, task_id: int, checkpoint_data: CheckpointData | dict[str, Any]
    ) -> TaskCheckpoint:
        """Persist (or update) a checkpoint for the given task.

        ``checkpoint_data`` may be a :class:`CheckpointData` instance or a raw
        mapping. Existing checkpoints for ``task_id`` are upserted so that the
        most recent state always wins.
        """
        payload = (
            checkpoint_data
            if isinstance(checkpoint_data, CheckpointData)
            else CheckpointData.from_dict(checkpoint_data)
        )
        if payload.task_id != task_id:
            payload.task_id = task_id

        session, owned = self._session_scope()
        try:
            task = session.get(AITask, task_id)
            if task is None:
                raise ValueError(f"AI task {task_id} does not exist")

            checkpoint = session.scalar(
                select(TaskCheckpoint).where(TaskCheckpoint.task_id == task_id)
            )
            data = payload.to_dict()
            if checkpoint is None:
                checkpoint = TaskCheckpoint(
                    task_id=task_id,
                    project_id=task.project_id,
                    checkpoint_data=data,
                )
                session.add(checkpoint)
            else:
                checkpoint.project_id = task.project_id
                checkpoint.checkpoint_data = data
                checkpoint.updated_at = datetime.utcnow()

            self._commit(session, owned)
            if owned:
                session.refresh(checkpoint)
            else:
                session.refresh(checkpoint)
            logger.info(
                "Saved checkpoint for task %s at phase %s (completed=%s/%s)",
                task_id,
                payload.current_phase,
                len(payload.completed_chapters),
                payload.total_chapters,
            )
            return checkpoint
        except Exception:
            if owned:
                session.rollback()
            raise
        finally:
            self._close(session, owned)

    def load_task_checkpoint(self, task_id: int) -> tuple[TaskCheckpoint, CheckpointData] | None:
        """Return the stored checkpoint for ``task_id`` or ``None``."""
        session, owned = self._session_scope()
        try:
            checkpoint = session.scalar(
                select(TaskCheckpoint).where(TaskCheckpoint.task_id == task_id)
            )
            if checkpoint is None:
                return None
            data = CheckpointData.from_dict(checkpoint.checkpoint_data or {})
            return checkpoint, data
        finally:
            self._close(session, owned)

    def load_latest_checkpoint(self, task_id: int) -> CheckpointData | None:
        """Return only the :class:`CheckpointData` for ``task_id`` or ``None``.

        Convenience wrapper used by the resume endpoint — it only needs the
        structured payload (no ORM object) to compute ``start_chapter`` and
        forward ``accumulated_context`` to the orchestrator.
        """
        result = self.load_task_checkpoint(task_id)
        if result is None:
            return None
        return result[1]

    def find_orphaned_running_tasks(self) -> list[AITask]:
        """Return all tasks in ``running`` state without a live worker thread."""
        session, owned = self._session_scope()
        try:
            running_tasks = list(
                session.scalars(select(AITask).where(AITask.status == "running"))
            )
            return [task for task in running_tasks if not self.is_thread_active(task.id)]
        finally:
            self._close(session, owned)

    def mark_orphaned_tasks_as_paused(self) -> list[int]:
        """Pause every orphan task and return the list of affected task IDs."""
        session, owned = self._session_scope()
        try:
            running_tasks = list(
                session.scalars(select(AITask).where(AITask.status == "running"))
            )
            paused: list[int] = []
            for task in running_tasks:
                if self.is_thread_active(task.id):
                    continue
                task.status = "paused"
                session.add(task)
                paused.append(task.id)
            self._commit(session, owned)
            if paused:
                logger.warning("Marked %d orphan tasks as paused: %s", len(paused), paused)
            return paused
        except Exception:
            if owned:
                session.rollback()
            raise
        finally:
            self._close(session, owned)

    def resume_task(self, task_id: int, project_id: int) -> tuple[AITask, CheckpointData] | None:
        """Reload checkpoint state and flip the task back to ``pending``.

        The caller is expected to schedule a new worker for the task. The
        original AITask is updated in place and the latest checkpoint data is
        returned so the worker can pick up from the last successful phase.
        """
        session, owned = self._session_scope()
        try:
            task = session.get(AITask, task_id)
            if task is None or task.project_id != project_id:
                return None

            checkpoint = session.scalar(
                select(TaskCheckpoint).where(TaskCheckpoint.task_id == task_id)
            )
            if checkpoint is None:
                return None

            task.status = "pending"
            task.error_message = None
            session.add(task)
            self._commit(session, owned)
            session.refresh(task)
            data = CheckpointData.from_dict(checkpoint.checkpoint_data or {})
            logger.info(
                "Resumed task %s from phase %s (completed=%s/%s)",
                task_id,
                data.current_phase,
                len(data.completed_chapters),
                data.total_chapters,
            )
            return task, data
        except Exception:
            if owned:
                session.rollback()
            raise
        finally:
            self._close(session, owned)

    def list_resumable_tasks(self, project_id: int) -> list[tuple[AITask, CheckpointData]]:
        """List every paused/failed task within a project that has a checkpoint."""
        session, owned = self._session_scope()
        try:
            rows = list(
                session.scalars(
                    select(TaskCheckpoint).where(TaskCheckpoint.project_id == project_id)
                )
            )
            results: list[tuple[AITask, CheckpointData]] = []
            for row in rows:
                task = session.get(AITask, row.task_id)
                if task is None or task.status not in {"paused", "failed"}:
                    continue
                results.append((task, CheckpointData.from_dict(row.checkpoint_data or {})))
            return results
        finally:
            self._close(session, owned)
