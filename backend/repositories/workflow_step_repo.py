from __future__ import annotations

from typing import Sequence

from sqlalchemy import select

from backend.models.workflow_step import WorkflowStepRun
from backend.repositories.base import BaseRepository


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

    def delete(self, step: WorkflowStepRun) -> None:
        self.session.delete(step)
