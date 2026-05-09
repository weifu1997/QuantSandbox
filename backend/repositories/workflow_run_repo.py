from __future__ import annotations

from typing import Sequence
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import WorkflowRun
from backend.models.workflow import WorkflowRunStatus
from backend.repositories.base import BaseRepository
from backend.utils.time import utcnow


class WorkflowRunRepository(BaseRepository[WorkflowRun]):
    def create(self, run: WorkflowRun) -> WorkflowRun:
        self.session.add(run)
        self.session.flush()
        return run

    def get(self, run_id: str) -> WorkflowRun | None:
        return self.session.get(WorkflowRun, run_id)

    def list_recent(self, limit: int = 20, status: str | None = None, user_id: str | None = None) -> Sequence[WorkflowRun]:
        stmt = select(WorkflowRun)
        if status:
            stmt = stmt.where(WorkflowRun.status == status)
        if user_id:
            stmt = stmt.where(WorkflowRun.user_id == user_id)
        stmt = stmt.order_by(WorkflowRun.created_at.desc()).limit(limit)
        return self.session.execute(stmt).scalars().all()

    def mark_stale_running_low_value_failed(self, stale_after_minutes: int = 60) -> list[WorkflowRun]:
        cutoff = utcnow() - timedelta(minutes=stale_after_minutes)
        stmt = (
            select(WorkflowRun)
            .where(WorkflowRun.workflow_type == 'low_value_discovery')
            .where(WorkflowRun.status == WorkflowRunStatus.RUNNING)
            .where(WorkflowRun.started_at.is_not(None))
            .where(WorkflowRun.started_at < cutoff)
        )
        runs = self.session.execute(stmt).scalars().all()
        for run in runs:
            run.status = WorkflowRunStatus.FAILED
            run.completed_at = utcnow()
            self.session.add(run)
        self.session.flush()
        return runs

    def delete(self, run: WorkflowRun) -> None:
        self.session.delete(run)
