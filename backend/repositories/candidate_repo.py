from __future__ import annotations

from typing import Sequence

from sqlalchemy import select

from backend.models import Candidate
from backend.repositories.base import BaseRepository


class CandidateRepository(BaseRepository[Candidate]):
    def create(self, candidate: Candidate) -> Candidate:
        self.session.add(candidate)
        self.session.flush()
        return candidate

    def get(self, candidate_id: str) -> Candidate | None:
        return self.session.get(Candidate, candidate_id)

    def list_by_workflow_run(self, workflow_run_id: str) -> Sequence[Candidate]:
        stmt = select(Candidate).where(Candidate.workflow_run_id == workflow_run_id).order_by(Candidate.created_at.asc())
        return self.session.execute(stmt).scalars().all()

    def list_by_status(self, workflow_run_id: str, status: str) -> Sequence[Candidate]:
        stmt = (
            select(Candidate)
            .where(Candidate.workflow_run_id == workflow_run_id, Candidate.status == status)
            .order_by(Candidate.created_at.asc())
        )
        return self.session.execute(stmt).scalars().all()

    def delete(self, candidate: Candidate) -> None:
        self.session.delete(candidate)
