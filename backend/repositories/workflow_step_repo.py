from __future__ import annotations

from typing import Sequence

from sqlalchemy import select

from backend.models.workflow import WorkflowStepStatus
from backend.models.workflow_step import WorkflowStepRun
from backend.repositories.base import BaseRepository
from backend.utils.time import utcnow


class WorkflowStepRunRepository(BaseRepository[WorkflowStepRun]):
    def create(self, step: WorkflowStepRun) -> WorkflowStepRun:
        self.session.add(step)
        self.session.flush()
        return step

    def get(self, step_id: str) -> WorkflowStepRun | None:
        return self.session.get(WorkflowStepRun, step_id)

    def list_by_workflow_run(self, workflow_run_id: str) -> Sequence[WorkflowStepRun]:
        stmt = (
            select(WorkflowStepRun)
            .where(WorkflowStepRun.workflow_run_id == workflow_run_id)
            .order_by(WorkflowStepRun.created_at.asc())
        )
        return self.session.execute(stmt).scalars().all()

    def mark_running_steps_failed_for_run_ids(self, run_ids: list[str]) -> int:
        if not run_ids:
            return 0
        stmt = select(WorkflowStepRun).where(
            WorkflowStepRun.workflow_run_id.in_(run_ids),
            WorkflowStepRun.status == WorkflowStepStatus.RUNNING,
        )
        steps = self.session.execute(stmt).scalars().all()
        for step in steps:
            step.status = WorkflowStepStatus.FAILED
            step.completed_at = utcnow()
            step.error_message = step.error_message or 'workflow recovered on startup after stale running state'
            self.session.add(step)
        self.session.flush()
        return len(steps)

    def delete(self, step: WorkflowStepRun) -> None:
        self.session.delete(step)
