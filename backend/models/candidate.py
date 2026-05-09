from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, JSON, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class CandidateStatus(str, Enum):
    PENDING = "pending"
    SELECTED = "selected"
    ELIMINATED = "eliminated"
    INSUFFICIENT_DATA = "insufficient_data"


class CandidateReviewResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INSUFFICIENT = "insufficient"


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[CandidateStatus] = mapped_column(
        SAEnum(CandidateStatus, name="candidate_status"), nullable=False, default=CandidateStatus.PENDING, index=True
    )
    reason: Mapped[dict | list | str | None] = mapped_column(JSON, nullable=True)
    data: Mapped[dict | list | str | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_candidate_created_at', 'created_at'),
    )

    workflow_run: Mapped["WorkflowRun"] = relationship("WorkflowRun", back_populates="candidates")
    reviews: Mapped[list["CandidateReview"]] = relationship(
        "CandidateReview", back_populates="candidate", cascade="all, delete-orphan"
    )


class CandidateReview(Base):
    __tablename__ = "candidate_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    candidate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    review_result: Mapped[CandidateReviewResult] = mapped_column(
        SAEnum(CandidateReviewResult, name="candidate_review_result"), nullable=False, index=True
    )
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_data: Mapped[dict | list | str | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="reviews")
