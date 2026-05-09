from __future__ import annotations

from typing import Sequence

from sqlalchemy import select

from backend.models import CandidateReview
from backend.repositories.base import BaseRepository


class CandidateReviewRepository(BaseRepository[CandidateReview]):
    def create(self, review: CandidateReview) -> CandidateReview:
        self.session.add(review)
        self.session.flush()
        return review

    def get(self, review_id: str) -> CandidateReview | None:
        return self.session.get(CandidateReview, review_id)

    def list_by_candidate(self, candidate_id: str) -> Sequence[CandidateReview]:
        stmt = (
            select(CandidateReview)
            .where(CandidateReview.candidate_id == candidate_id)
            .order_by(CandidateReview.created_at.asc())
        )
        return self.session.execute(stmt).scalars().all()

    def delete(self, review: CandidateReview) -> None:
        self.session.delete(review)
