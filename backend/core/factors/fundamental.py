from __future__ import annotations

import pandas as pd

from .base import Factor


def _pick_numeric_series(df: pd.DataFrame, candidates: list[str], factor_name: str) -> pd.Series:
    for column in candidates:
        if column in df.columns:
            return pd.to_numeric(df[column], errors="coerce").rename(factor_name)
    return pd.Series(index=df.index, dtype="float64", name=factor_name)


class PeTtm(Factor):
    def __init__(self):
        super().__init__(
            name="pe_ttm",
            category="fundamental",
            description="滚动市盈率（优先读取 dataframe 已有列）",
            params_schema={},
        )

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return _pick_numeric_series(df, ["pe_ttm_num", "pe_ttm", "pe"], self.name)


class Pb(Factor):
    def __init__(self):
        super().__init__(
            name="pb",
            category="fundamental",
            description="市净率 PB（优先读取 dataframe 已有列）",
            params_schema={},
        )

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return _pick_numeric_series(df, ["pb_num", "pb"], self.name)


class DividendYield(Factor):
    def __init__(self):
        super().__init__(
            name="dividend_yield",
            category="fundamental",
            description="股息率（优先读取 dataframe 已有列）",
            params_schema={},
        )

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return _pick_numeric_series(df, ["dividend_yield_num", "dividend_yield"], self.name)
