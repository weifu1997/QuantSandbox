from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    status: str = "success"
    data: Any = None
    message: str | None = None
    error: Any = None


# ============================================================
# Sprint D 策略体系 — 响应模型（Slice 3: API schema 标准化）
# ============================================================

class BacktestKlineItem(BaseModel):
    """单根 K 线 + 仓位信息"""
    date: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    target_weight: float = 0.0
    total_equity: float = 0.0
    position_mode: str = ""


class BacktestMetadata(BaseModel):
    """单标的回测指标"""
    ticker: str = ""
    name: str = ""
    display_name: str = ""
    start_date: str = ""
    end_date: str = ""
    final_equity: float = 0.0
    total_return: float = 0.0
    trade_count: int = 0
    position_mode: str = ""
    active_target_weight: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    final_shares: int = 0


class BacktestSummaryRow(BaseModel):
    """多标的回测汇总行"""
    ticker: str = ""
    display_name: str = ""
    name: str = ""
    strategy: str = ""
    final_equity: float = 0.0
    return_rate: float = 0.0
    trade_count: int = 0
    position_mode: str = ""
    active_target_weight: float = 0.0


class StrategyBacktestDetail(BaseModel):
    """单标的回测详情（包含 klines/logs）"""
    ticker: str = ""
    name: str = ""
    display_name: str = ""
    strategy_name: str = ""
    strategy_meta: dict = Field(default_factory=dict)
    targets: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    klines: list[dict] = Field(default_factory=list)
    logs: list[dict] = Field(default_factory=list)


class StrategyBacktestEnvelope(BaseModel):
    """统一的策略回测响应 envelope（单标的/多标的）"""
    status: str = "success"
    mode: str = "multi"  # "single" | "multi"
    strategy_name: str = ""
    strategy_meta: dict = Field(default_factory=dict)
    selection_source: str = ""
    requested_tickers: list[str] = Field(default_factory=list)
    resolved_tickers: list[str] = Field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    count: int = 0
    data: list[dict] = Field(default_factory=list)  # summary rows
    details: list[dict] = Field(default_factory=list)  # full detail objects
    errors: list[dict] = Field(default_factory=list)


class WalkForwardTaskSubmitResponse(BaseModel):
    """Walk-Forward 异步任务提交响应"""
    status: str = "accepted"
    data: dict = Field(default_factory=dict)  # {"task_id": "..."}


class WalkForwardTaskQueryResponse(BaseModel):
    """Walk-Forward 异步任务查询响应"""
    status: str = "success"
    data: dict = Field(default_factory=dict)  # task_id, task_status, progress, result, error


class PortfolioBacktestResponse(BaseModel):
    """组合级回测响应"""
    status: str = "success"
    strategy_name: str = ""
    ticker_count: int = 0
    resolved_tickers: list[str] = Field(default_factory=list)
    portfolio_metrics: dict = Field(default_factory=dict)
    portfolio_equity: list[float] = Field(default_factory=list)
    per_ticker: dict[str, dict] = Field(default_factory=dict)
    logs: list[dict] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)


class PortfolioOptimizeResponse(BaseModel):
    """组合级参数优化响应"""
    status: str = "success"
    strategy_name: str = ""
    strategy_meta: dict = Field(default_factory=dict)
    ticker_count: int = 0
    resolved_tickers: list[str] = Field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    objective: str = ""
    param_grid: dict = Field(default_factory=dict)
    per_ticker: dict[str, dict] = Field(default_factory=dict)
    fetch_errors: list[dict] = Field(default_factory=list)


class SummaryResponse(BaseModel):
    """/api/summary 响应"""
    status: str = "success"
    data: list[dict] = Field(default_factory=list)
    data_source: str = ""
    fetch_note: str = ""
    errors: list[dict] = Field(default_factory=list)


class DetailResponse(BaseModel):
    """/api/detail/{ticker} 响应"""
    status: str = "success"
    ticker: str = ""
    name: str = ""
    display_name: str = ""
    metadata: dict = Field(default_factory=dict)
    klines: list[dict] = Field(default_factory=list)
    logs: list[dict] = Field(default_factory=list)


class MXQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
