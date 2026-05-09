from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, JSON, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.utils.time import utcnow


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class WatchlistEntry(Base):
    __tablename__ = "watchlist_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    entry_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[RiskLevel] = mapped_column(
        SAEnum(RiskLevel, name="watchlist_risk_level"), nullable=False, default=RiskLevel.UNKNOWN
    )
    catalyst_factors: Mapped[dict | list | str | None] = mapped_column(JSON, nullable=True)
    board: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pe_ttm: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pb: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latest_price: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dividend_yield: Mapped[str | None] = mapped_column(String(32), nullable=True)
    month_return: Mapped[str | None] = mapped_column(String(32), nullable=True)
    st_flag: Mapped[str | None] = mapped_column(String(16), nullable=True)
    watch_price_zone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    entry_date: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utcnow)

    __table_args__ = (
        Index('idx_watchlist_created_at', 'created_at'),
    )

    workflow_run: Mapped["WorkflowRun"] = relationship("WorkflowRun", back_populates="watchlist_entries")

