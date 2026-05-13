from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AlphaDatasetRequest:
    tickers: list[str]
    start_date: str
    end_date: str
    factors: list[str]
    horizons: list[int] = field(default_factory=lambda: [5, 20, 60])
    price_adjust: str = "qfq"


@dataclass(slots=True)
class AlphaDatasetResult:
    rows: int
    tickers: list[str]
    factors: list[str]
    horizons: list[int]
    valid_sample_ratio: float
    invalid_reasons: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class HorizonICStats:
    horizon: int
    ic_mean: float = 0.0
    ic_std: float = 0.0
    ic_ir: float = 0.0
    rank_ic_mean: float = 0.0
    rank_ic_std: float = 0.0
    rank_ic_ir: float = 0.0
    positive_ic_ratio: float = 0.0
    sample_count: int = 0
    missing_ratio: float = 0.0
    monthly_ic_series: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class FactorICReport:
    factor_name: str
    horizons: dict[int, HorizonICStats]
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GroupBacktestReport:
    factor_name: str
    horizon: int
    groups: int
    rebalance_frequency: str
    group_return_by_group: dict[str, float] = field(default_factory=dict)
    equity_curve_by_group: dict[str, list[float]] = field(default_factory=dict)
    long_short_return: float = 0.0
    monotonicity_score: float = 0.0
    annual_return_by_group: dict[str, float] = field(default_factory=dict)
    max_drawdown_by_group: dict[str, float] = field(default_factory=dict)
    win_rate_by_group: dict[str, float] = field(default_factory=dict)
    turnover_by_group: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TopNBacktestReport:
    factor_name: str
    horizon: int
    top_n: int
    rebalance_frequency: str
    weighting: str
    benchmark_name: str
    annual_return: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    volatility: float = 0.0
    turnover: float = 0.0
    win_rate: float = 0.0
    cost_paid: float = 0.0
    excess_return_vs_equal_weight: float = 0.0
    excess_return_vs_benchmark: float = 0.0
    holdings_by_rebalance_date: dict[str, list[str]] = field(default_factory=dict)
    equity_curve: list[float] = field(default_factory=list)
    benchmark_equity_curve: list[float] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AlphaResearchFactorSummary:
    factor_name: str
    horizon: int
    ic_mean: float = 0.0
    rank_ic_mean: float = 0.0
    ic_ir: float = 0.0
    positive_ic_ratio: float = 0.0
    missing_ratio: float = 0.0
    sample_count: int = 0
    group_long_short_return: float = 0.0
    group_monotonicity_score: float = 0.0
    topn_total_return: float = 0.0
    topn_annual_return: float = 0.0
    topn_max_drawdown: float = 0.0
    topn_sharpe: float = 0.0
    topn_turnover: float = 0.0
    topn_cost_paid: float = 0.0
    topn_excess_return_vs_equal_weight: float = 0.0
    topn_excess_return_vs_benchmark: float = 0.0
    verdict: str = "needs_review"
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AlphaResearchConclusion:
    recommended_factors: list[str] = field(default_factory=list)
    rejected_factors: list[str] = field(default_factory=list)
    watchlist_factors: list[str] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AlphaResearchReport:
    title: str
    generated_at: str
    output_format: str
    config: dict[str, Any] = field(default_factory=dict)
    dataset: dict[str, Any] = field(default_factory=dict)
    factor_summaries: list[AlphaResearchFactorSummary] = field(default_factory=list)
    factor_details: dict[str, dict[str, Any]] = field(default_factory=dict)
    topn_strategy: dict[str, Any] = field(default_factory=dict)
    conclusion: AlphaResearchConclusion = field(default_factory=AlphaResearchConclusion)
    markdown: str = ""
