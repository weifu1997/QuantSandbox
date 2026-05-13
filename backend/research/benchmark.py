from __future__ import annotations

import math

import pandas as pd



def _equity_curve_from_returns(returns: list[float]) -> list[float]:
    curve: list[float] = []
    equity = 1.0
    for value in returns:
        equity *= (1.0 + float(value))
        curve.append(float(equity))
    return curve



def run_equal_weight_universe_benchmark(dataset: pd.DataFrame, future_col: str) -> dict[str, object]:
    grouped = []
    for raw_date, group in dataset.groupby("date", sort=True):
        valid = group.copy()
        if "is_valid_sample" in valid.columns:
            valid = valid.loc[valid["is_valid_sample"] == True].copy()
        valid[future_col] = pd.to_numeric(valid[future_col], errors="coerce")
        valid = valid.dropna(subset=[future_col])
        if valid.empty:
            continue
        grouped.append((pd.Timestamp(raw_date), float(valid[future_col].mean())))

    returns = [item[1] for item in grouped]
    dates = [item[0].strftime("%Y-%m-%d") for item in grouped]
    return {
        "name": "equal_weight_universe",
        "dates": dates,
        "returns": returns,
        "equity_curve": _equity_curve_from_returns(returns),
    }



def run_buy_hold_universe_average_benchmark(dataset: pd.DataFrame, future_col: str) -> dict[str, object]:
    # v1: 在只有 future_return 面板、没有日频真实持仓路径的前提下，先用逐期全池等权均值近似 buy-hold universe average
    result = run_equal_weight_universe_benchmark(dataset, future_col)
    result["name"] = "buy_hold_universe_average"
    return result



def run_benchmark(dataset: pd.DataFrame, future_col: str, benchmark: str) -> dict[str, object]:
    name = str(benchmark or "equal_weight_universe")
    if name == "equal_weight_universe":
        return run_equal_weight_universe_benchmark(dataset, future_col)
    if name == "buy_hold_universe_average":
        return run_buy_hold_universe_average_benchmark(dataset, future_col)
    raise ValueError(f"unsupported benchmark: {benchmark}")
