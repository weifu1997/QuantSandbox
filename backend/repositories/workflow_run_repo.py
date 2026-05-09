from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import WorkflowRun
from backend.repositories.base import BaseRepository


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

    def delete(self, run: WorkflowRun) -> None:
        self.session.delete(run)
