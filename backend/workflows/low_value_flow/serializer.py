from __future__ import annotations

from typing import Any

from backend.models import CandidateStatus, CandidateReviewResult


def candidate_status_from_logic(label: str) -> CandidateStatus:
    mapping = {
        "selected": CandidateStatus.SELECTED,
        "eliminated": CandidateStatus.ELIMINATED,
        "insufficient_data": CandidateStatus.INSUFFICIENT_DATA,
        "pending": CandidateStatus.PENDING,
    }
    return mapping.get(label, CandidateStatus.PENDING)


def review_result_from_status(status: str) -> CandidateReviewResult:
    mapping = {
        "pass": CandidateReviewResult.PASS,
        "fail": CandidateReviewResult.FAIL,
        "insufficient": CandidateReviewResult.INSUFFICIENT,
    }
    return mapping.get(status, CandidateReviewResult.INSUFFICIENT)
