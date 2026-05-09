from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class LowValueRunRequest(BaseModel):
    use_default_template: bool = True
    custom_query: Optional[str] = None
    user_id: Optional[str] = None
    batch_size: int = Field(default=5, ge=1, le=20)
    pool_group_filter: Optional[str] = None


class WatchlistUpdateRequest(BaseModel):
    entry_reason: Optional[str] = None
    risk_level: Optional[str] = None
    catalyst_factors: Any = None
    watch_price_zone: Optional[str] = None
    board: Optional[str] = None
    pe_ttm: Optional[str] = None
    pb: Optional[str] = None
    latest_price: Optional[str] = None
    dividend_yield: Optional[str] = None
    month_return: Optional[str] = None
    st_flag: Optional[str] = None
    pool_group: Optional[str] = None
    position_age: Optional[str] = None
    left_side_grade: Optional[str] = None
    stop_loss_price: Optional[float] = None
    target_price: Optional[float] = None
    buy_date: Optional[datetime] = None
    time_circuit_breaker_start: Optional[datetime] = None
    catalyst_signal: Optional[str] = None
    exit_condition: Optional[str] = None
    review_count: Optional[int] = None
    last_review_at: Optional[datetime] = None
    observation_note: Optional[str] = None


class VolumeVerifyRequest(BaseModel):
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class LeftSideRankRequest(BaseModel):
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class APIResponse(BaseModel):
    status: str = "success"
    data: Any = None


class MXQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
