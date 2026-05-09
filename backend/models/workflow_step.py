from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, JSON, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.workflow import WorkflowStepStatus


class WorkflowStepRun(Base):
    __tablename__ = "workflow_step_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[WorkflowStepStatus] = mapped_column(
        SAEnum(WorkflowStepStatus, name="workflow_step_status"), nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    result_data: Mapped[dict | list | str | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_workflow_step_created_at', 'created_at'),
    )

    workflow_run: Mapped["WorkflowRun"] = relationship("WorkflowRun", back_populates="step_runs")

