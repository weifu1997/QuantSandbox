from __future__ import annotations

from typing import Iterable

import pandas as pd

from backend.api.config_endpoints import get_data_center
from backend.core.factors import FactorRegistry, get_factor_registry


def add_future_returns(df: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    result = df.copy()
    close = pd.to_numeric(result["close"], errors="coerce")
    for horizon in horizons:
        result[f"future_return_{horizon}d"] = close.shift(-horizon) / close - 1.0
    return result


def align_factor_values(
    df: pd.DataFrame,
    factor_names: list[str],
    factor_registry=None,
) -> pd.DataFrame:
    result = df.copy()
    registry = factor_registry or get_factor_registry()
    for factor_name in factor_names:
        if hasattr(registry, "compute_factor"):
            series = registry.compute_factor(factor_name, result)
        else:
            factor = registry.get(factor_name)
            series = factor.compute(result)
        clean = pd.to_numeric(series, errors="coerce").replace([float("inf"), float("-inf")], pd.NA)
        result[f"factor:{factor_name}"] = clean
    return result


def _mark_validity(df: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    result = df.copy()
    result["is_valid_sample"] = True
    result["missing_reason"] = ""

    volume = pd.to_numeric(result.get("volume"), errors="coerce")
    invalid_volume = volume.isna() | (volume <= 0)
    result.loc[invalid_volume, "is_valid_sample"] = False
    result.loc[invalid_volume, "missing_reason"] = "non_positive_volume"

    for horizon in horizons:
        col = f"future_return_{horizon}d"
        missing_future = result[col].isna() & (result["missing_reason"] == "")
        result.loc[missing_future, "is_valid_sample"] = False
        result.loc[missing_future, "missing_reason"] = f"missing_future_return_{horizon}d"

    factor_cols = [col for col in result.columns if col.startswith("factor:")]
    if factor_cols:
        factor_missing = result[factor_cols].isna().any(axis=1) & (result["missing_reason"] == "")
        result.loc[factor_missing, "is_valid_sample"] = False
        result.loc[factor_missing, "missing_reason"] = "factor_value_missing"

    return result


def _normalize_frame(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    result = df.copy()
    if result.empty:
        return result
    result["date"] = pd.to_datetime(result["date"])
    result = result.sort_values("date").reset_index(drop=True)
    result["ticker"] = ticker
    base_cols = ["open", "high", "low", "close", "volume"]
    for col in base_cols:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")
    return result


def build_alpha_dataset(
    tickers: list[str],
    start_date: str,
    end_date: str,
    factors: list[str],
    horizons: list[int],
    data_center=None,
    factor_registry: FactorRegistry | None = None,
) -> pd.DataFrame:
    dc = data_center or get_data_center()
    registry = factor_registry or get_factor_registry()
    frames: list[pd.DataFrame] = []

    for ticker in tickers:
        raw_df = dc.fetch_stock_data(ticker, start_date=start_date, end_date=end_date)
        if raw_df is None or raw_df.empty:
            continue
        one = _normalize_frame(raw_df, ticker)
        one = align_factor_values(one, factors, factor_registry=registry)
        one = add_future_returns(one, horizons)
        one = _mark_validity(one, horizons)
        frames.append(one)

    if not frames:
        columns = [
            "date", "ticker", "open", "high", "low", "close", "volume",
            *[f"factor:{name}" for name in factors],
            *[f"future_return_{h}d" for h in horizons],
            "is_valid_sample", "missing_reason",
        ]
        return pd.DataFrame(columns=columns)

    dataset = pd.concat(frames, ignore_index=True, sort=False)
    dataset = dataset.sort_values(["date", "ticker"]).reset_index(drop=True)
    return dataset
