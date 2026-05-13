from __future__ import annotations

import math

import pandas as pd

from backend.research.benchmark import run_benchmark
from backend.research.schemas import TopNBacktestReport



def _compute_max_drawdown(curve: list[float]) -> float:
    if not curve:
        return 0.0
    peak = curve[0]
    max_dd = 0.0
    for value in curve:
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, value / peak - 1.0)
    return float(max_dd)



def _annualize_from_curve(curve: list[float], periods_per_year: int = 252) -> float:
    if len(curve) < 2 or curve[0] <= 0:
        return 0.0
    years = max((len(curve) - 1) / periods_per_year, 1 / periods_per_year)
    return float((curve[-1] / curve[0]) ** (1 / years) - 1)



def _volatility(returns: list[float], periods_per_year: int = 252) -> float:
    if len(returns) <= 1:
        return 0.0
    series = pd.Series(returns, dtype="float64")
    return float(series.std(ddof=1) * math.sqrt(periods_per_year)) if not series.empty else 0.0



def _sharpe(returns: list[float], periods_per_year: int = 252) -> float:
    if len(returns) <= 1:
        return 0.0
    series = pd.Series(returns, dtype="float64")
    std = float(series.std(ddof=1)) if not series.empty else 0.0
    if std <= 0:
        return 0.0
    mean = float(series.mean())
    return float(mean / std * math.sqrt(periods_per_year))



def _select_rebalance_dates(dates: list[pd.Timestamp], frequency: str) -> set[pd.Timestamp]:
    if not dates:
        return set()
    normalized = frequency.upper()
    if normalized == "D":
        return set(dates)
    series = pd.Series(dates)
    if normalized == "W":
        periods = series.dt.to_period("W")
    elif normalized == "M":
        periods = series.dt.to_period("M")
    else:
        raise ValueError(f"unsupported rebalance_frequency: {frequency}")
    mask = periods != periods.shift(1)
    return set(series[mask].tolist())



def _compute_weights(bucket: pd.DataFrame, factor_col: str, weighting: str) -> pd.Series:
    if weighting == "equal":
        return pd.Series([1.0 / len(bucket)] * len(bucket), index=bucket.index, dtype="float64")
    if weighting == "score":
        scores = pd.to_numeric(bucket[factor_col], errors="coerce")
        shifted = scores - scores.min()
        positive = shifted + 1e-9
        total = float(positive.sum())
        if total <= 0:
            return pd.Series([1.0 / len(bucket)] * len(bucket), index=bucket.index, dtype="float64")
        return positive / total
    raise ValueError(f"unsupported weighting: {weighting}")



def run_topn_backtest(
    dataset: pd.DataFrame,
    factor_name: str,
    horizon: int = 20,
    top_n: int = 10,
    rebalance_frequency: str = "W",
    weighting: str = "equal",
    transaction_cost_bps: float = 10,
    benchmark: str = "equal_weight_universe",
) -> TopNBacktestReport:
    factor_col = f"factor:{factor_name}"
    future_col = f"future_return_{horizon}d"
    if factor_col not in dataset.columns:
        raise KeyError(f"missing factor column: {factor_col}")
    if future_col not in dataset.columns:
        raise KeyError(f"missing future return column: {future_col}")

    warnings: list[str] = []
    dates = sorted(pd.to_datetime(dataset["date"]).dropna().unique().tolist())
    rebalance_dates = _select_rebalance_dates(dates, rebalance_frequency)

    portfolio_returns_before_cost: list[float] = []
    portfolio_returns_after_cost: list[float] = []
    holdings_by_rebalance_date: dict[str, list[str]] = {}
    previous_holdings: tuple[str, ...] = tuple()
    turnover_series: list[float] = []
    total_cost_paid = 0.0

    for raw_date, group in dataset.groupby("date", sort=True):
        date = pd.Timestamp(raw_date)
        valid = group.copy()
        if "is_valid_sample" in valid.columns:
            valid = valid.loc[valid["is_valid_sample"] == True].copy()
        valid[factor_col] = pd.to_numeric(valid[factor_col], errors="coerce")
        valid[future_col] = pd.to_numeric(valid[future_col], errors="coerce")
        valid = valid.dropna(subset=[factor_col, future_col])

        if valid.empty:
            warnings.append(f"date={date.strftime('%Y-%m-%d')} no valid rows")
            continue

        ranked = valid.sort_values([factor_col, "ticker"], ascending=[False, True]).head(top_n).copy()
        if ranked.empty:
            warnings.append(f"date={date.strftime('%Y-%m-%d')} top_n selection empty")
            continue

        weights = _compute_weights(ranked, factor_col, weighting)
        gross_return = float((weights * ranked[future_col]).sum())
        portfolio_returns_before_cost.append(gross_return)

        current_holdings = tuple(sorted(ranked["ticker"].astype(str).tolist()))
        if date in rebalance_dates:
            holdings_by_rebalance_date[date.strftime('%Y-%m-%d')] = list(current_holdings)
            if not previous_holdings:
                turnover = 1.0
            else:
                changed = len(set(previous_holdings).symmetric_difference(current_holdings))
                denom = max(len(previous_holdings) + len(current_holdings), 1)
                turnover = changed / denom
            previous_holdings = current_holdings
        else:
            turnover = 0.0

        turnover_series.append(float(turnover))
        cost = float(turnover * (transaction_cost_bps / 10000.0))
        total_cost_paid += cost
        portfolio_returns_after_cost.append(gross_return - cost)

    equity_curve = []
    equity = 1.0
    for value in portfolio_returns_after_cost:
        equity *= (1.0 + value)
        equity_curve.append(float(equity))

    benchmark_result = run_benchmark(dataset, future_col, benchmark)
    benchmark_curve = list(benchmark_result["equity_curve"])
    benchmark_total_return = (benchmark_curve[-1] - 1.0) if benchmark_curve else 0.0

    equal_weight_result = run_benchmark(dataset, future_col, "equal_weight_universe")
    equal_weight_curve = list(equal_weight_result["equity_curve"])
    equal_weight_total_return = (equal_weight_curve[-1] - 1.0) if equal_weight_curve else 0.0

    total_return = (equity_curve[-1] - 1.0) if equity_curve else 0.0
    win_rate = (
        sum(1 for value in portfolio_returns_after_cost if value > 0) / len(portfolio_returns_after_cost)
        if portfolio_returns_after_cost
        else 0.0
    )
    average_turnover = sum(turnover_series) / len(turnover_series) if turnover_series else 0.0

    return TopNBacktestReport(
        factor_name=factor_name,
        horizon=horizon,
        top_n=top_n,
        rebalance_frequency=rebalance_frequency,
        weighting=weighting,
        benchmark_name=str(benchmark_result["name"]),
        annual_return=_annualize_from_curve(equity_curve) if equity_curve else 0.0,
        total_return=float(total_return),
        max_drawdown=_compute_max_drawdown(equity_curve),
        sharpe=_sharpe(portfolio_returns_after_cost),
        volatility=_volatility(portfolio_returns_after_cost),
        turnover=float(average_turnover),
        win_rate=float(win_rate),
        cost_paid=float(total_cost_paid),
        excess_return_vs_equal_weight=float(total_return - equal_weight_total_return),
        excess_return_vs_benchmark=float(total_return - benchmark_total_return),
        holdings_by_rebalance_date=holdings_by_rebalance_date,
        equity_curve=equity_curve,
        benchmark_equity_curve=benchmark_curve,
        warnings=warnings,
    )
