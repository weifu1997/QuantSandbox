from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class LowValueRunRequest(BaseModel):
    use_default_template: bool = True
    custom_query: Optional[str] = None
    user_id: Optional[str] = None
    batch_size: int = Field(default=5, ge=1, le=20)


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


class APIResponse(BaseModel):
    status: str = "success"
    data: Any = None


class MXQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
