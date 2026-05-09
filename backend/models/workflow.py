from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SAEnum, Integer, JSON, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class WorkflowRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[WorkflowRunStatus] = mapped_column(
        SAEnum(WorkflowRunStatus, name="workflow_run_status"),
        nullable=False,
        default=WorkflowRunStatus.PENDING,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index('idx_workflow_run_created_at', 'created_at'),
    )

    step_runs: Mapped[list["WorkflowStepRun"]] = relationship(
        "WorkflowStepRun", back_populates="workflow_run", cascade="all, delete-orphan"
    )
    candidates: Mapped[list["Candidate"]] = relationship(
        "Candidate", back_populates="workflow_run", cascade="all, delete-orphan"
    )
    watchlist_entries: Mapped[list["WatchlistEntry"]] = relationship(
        "WatchlistEntry", back_populates="workflow_run", cascade="all, delete-orphan"
    )
