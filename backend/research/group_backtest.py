from __future__ import annotations

import math

import pandas as pd

from backend.research.factor_library import ResearchFactorLibrary, get_research_factor_library
from backend.research.schemas import GroupBacktestReport



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
    total_return = curve[-1] / curve[0] - 1.0
    years = max((len(curve) - 1) / periods_per_year, 1 / periods_per_year)
    if curve[-1] <= 0:
        return -1.0
    return float((curve[-1] / curve[0]) ** (1 / years) - 1)



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



def run_group_backtest(
    dataset: pd.DataFrame,
    factor_name: str,
    horizon: int = 20,
    groups: int = 5,
    rebalance_frequency: str = "D",
    factor_library: ResearchFactorLibrary | None = None,
) -> GroupBacktestReport:
    library = factor_library or get_research_factor_library()
    factor = library.get(factor_name)
    factor_col = f"factor:{factor_name}"
    future_col = f"future_return_{horizon}d"
    if factor_col not in dataset.columns:
        raise KeyError(f"missing factor column: {factor_col}")
    if future_col not in dataset.columns:
        raise KeyError(f"missing future return column: {future_col}")

    warnings: list[str] = []
    labels = [f"Q{i}" for i in range(1, groups + 1)]
    returns_by_group: dict[str, list[float]] = {label: [] for label in labels}
    turnover_counts: dict[str, int] = {label: 0 for label in labels}
    previous_holdings: dict[str, tuple[str, ...]] = {label: tuple() for label in labels}

    dates = sorted(pd.to_datetime(dataset["date"]).dropna().unique().tolist())
    rebalance_dates = _select_rebalance_dates(dates, rebalance_frequency)

    for raw_date, group_df in dataset.groupby("date", sort=True):
        date = pd.Timestamp(raw_date)
        valid = group_df.copy()
        if "is_valid_sample" in valid.columns:
            valid = valid.loc[valid["is_valid_sample"] == True].copy()
        valid[factor_col] = pd.to_numeric(valid[factor_col], errors="coerce")
        valid[future_col] = pd.to_numeric(valid[future_col], errors="coerce")
        valid = valid.dropna(subset=[factor_col, future_col])

        if len(valid) < groups:
            warnings.append(f"date={date.strftime('%Y-%m-%d')} cross-section too small for {groups} groups")
            continue

        sort_values = valid[factor_col]
        if factor.higher_is_better is False:
            sort_values = -sort_values
        ranked = valid.assign(_sort_factor=sort_values).sort_values(["_sort_factor", "ticker"], ascending=[True, True]).reset_index(drop=True)
        ranked["_group"] = pd.qcut(ranked.index, q=groups, labels=labels)

        for label in labels:
            bucket = ranked.loc[ranked["_group"] == label].copy()
            if bucket.empty:
                warnings.append(f"date={date.strftime('%Y-%m-%d')} {label} empty after grouping")
                continue
            period_return = float(bucket[future_col].mean())
            returns_by_group[label].append(period_return)

            if date in rebalance_dates:
                current_holdings = tuple(sorted(bucket["ticker"].astype(str).tolist()))
                prev_holdings = previous_holdings[label]
                if not prev_holdings:
                    turnover = 1.0
                else:
                    changed = len(set(prev_holdings).symmetric_difference(current_holdings))
                    denom = max(len(prev_holdings) + len(current_holdings), 1)
                    turnover = changed / denom
                turnover_counts[label] += turnover
                previous_holdings[label] = current_holdings

    equity_curve_by_group: dict[str, list[float]] = {}
    group_return_by_group: dict[str, float] = {}
    annual_return_by_group: dict[str, float] = {}
    max_drawdown_by_group: dict[str, float] = {}
    win_rate_by_group: dict[str, float] = {}
    turnover_by_group: dict[str, float] = {}

    for label in labels:
        curve = [1.0]
        for value in returns_by_group[label]:
            curve.append(curve[-1] * (1.0 + value))
        curve_without_seed = curve[1:] if len(curve) > 1 else []
        equity_curve_by_group[label] = curve_without_seed
        group_return_by_group[label] = float(curve[-1] - 1.0)
        annual_return_by_group[label] = _annualize_from_curve(curve)
        max_drawdown_by_group[label] = _compute_max_drawdown(curve)
        wins = [value for value in returns_by_group[label] if value > 0]
        win_rate_by_group[label] = (len(wins) / len(returns_by_group[label])) if returns_by_group[label] else 0.0
        turnover_by_group[label] = (
            turnover_counts[label] / max(len(returns_by_group[label]), 1)
            if returns_by_group[label]
            else 0.0
        )

    ordered_returns = [group_return_by_group[label] for label in labels]
    monotonic_hits = 0
    for left, right in zip(ordered_returns[:-1], ordered_returns[1:]):
        if right > left:
            monotonic_hits += 1
    monotonicity_score = monotonic_hits / (groups - 1) if groups > 1 else 0.0
    long_short_return = group_return_by_group.get(labels[-1], 0.0) - group_return_by_group.get(labels[0], 0.0)

    return GroupBacktestReport(
        factor_name=factor_name,
        horizon=horizon,
        groups=groups,
        rebalance_frequency=rebalance_frequency,
        group_return_by_group=group_return_by_group,
        equity_curve_by_group=equity_curve_by_group,
        long_short_return=float(long_short_return),
        monotonicity_score=float(monotonicity_score),
        annual_return_by_group=annual_return_by_group,
        max_drawdown_by_group=max_drawdown_by_group,
        win_rate_by_group=win_rate_by_group,
        turnover_by_group=turnover_by_group,
        warnings=warnings,
    )
