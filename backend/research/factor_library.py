from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from backend.core.factors import get_factor_registry


@dataclass(slots=True)
class ResearchFactor:
    name: str
    category: str
    description: str
    higher_is_better: bool
    required_columns: list[str]
    min_periods: int
    compute: Callable[[pd.DataFrame], pd.Series]


class ResearchFactorLibrary:
    def __init__(self):
        self._core_registry = get_factor_registry()
        self._factors: dict[str, ResearchFactor] = {}
        self._register_defaults()

    def register(self, factor: ResearchFactor) -> None:
        self._factors[factor.name] = factor

    def get(self, name: str) -> ResearchFactor:
        if name not in self._factors:
            raise KeyError(f"未知研究因子: {name}")
        return self._factors[name]

    def list_names(self) -> list[str]:
        return list(self._factors.keys())

    def compute_factor(self, name: str, df: pd.DataFrame) -> pd.Series:
        factor = self.get(name)
        series = factor.compute(df)
        return pd.to_numeric(series, errors="coerce").replace([float("inf"), float("-inf")], pd.NA).rename(name)

    def _register_defaults(self) -> None:
        self.register(
            ResearchFactor(
                name="momentum_20d",
                category="momentum",
                description="20 日动量",
                higher_is_better=True,
                required_columns=["close"],
                min_periods=20,
                compute=lambda df: pd.to_numeric(df["close"], errors="coerce") / pd.to_numeric(df["close"], errors="coerce").shift(20) - 1,
            )
        )
        self.register(
            ResearchFactor(
                name="momentum_60d",
                category="momentum",
                description="60 日动量",
                higher_is_better=True,
                required_columns=["close"],
                min_periods=60,
                compute=lambda df: pd.to_numeric(df["close"], errors="coerce") / pd.to_numeric(df["close"], errors="coerce").shift(60) - 1,
            )
        )
        self.register(
            ResearchFactor(
                name="momentum_120d",
                category="momentum",
                description="120 日动量",
                higher_is_better=True,
                required_columns=["close"],
                min_periods=120,
                compute=lambda df: pd.to_numeric(df["close"], errors="coerce") / pd.to_numeric(df["close"], errors="coerce").shift(120) - 1,
            )
        )
        self.register(
            ResearchFactor(
                name="momentum_20d_skip5d",
                category="momentum",
                description="跳过最近 5 日的 20 日动量",
                higher_is_better=True,
                required_columns=["close"],
                min_periods=25,
                compute=lambda df: pd.to_numeric(df["close"], errors="coerce").shift(5) / pd.to_numeric(df["close"], errors="coerce").shift(25) - 1,
            )
        )
        self.register(
            ResearchFactor(
                name="reversal_5d",
                category="reversal",
                description="5 日反转",
                higher_is_better=True,
                required_columns=["close"],
                min_periods=5,
                compute=lambda df: -(
                    pd.to_numeric(df["close"], errors="coerce") / pd.to_numeric(df["close"], errors="coerce").shift(5) - 1
                ),
            )
        )
        self.register(
            ResearchFactor(
                name="rsi_14",
                category="reversal",
                description="14 日 RSI",
                higher_is_better=False,
                required_columns=["close"],
                min_periods=14,
                compute=lambda df: self._core_registry.get("rsi_value").compute(df),
            )
        )
        self.register(
            ResearchFactor(
                name="bollinger_position_20",
                category="reversal",
                description="20 日布林位置",
                higher_is_better=False,
                required_columns=["close"],
                min_periods=20,
                compute=lambda df: self._core_registry.get("bollinger_position").compute(df),
            )
        )
        self.register(
            ResearchFactor(
                name="ma5_ma20",
                category="trend",
                description="MA5/MA20 - 1",
                higher_is_better=True,
                required_columns=["close"],
                min_periods=20,
                compute=lambda df: self._ratio_of_rolling_means(df, 5, 20),
            )
        )
        self.register(
            ResearchFactor(
                name="ma20_ma60",
                category="trend",
                description="MA20/MA60 - 1",
                higher_is_better=True,
                required_columns=["close"],
                min_periods=60,
                compute=lambda df: self._ratio_of_rolling_means(df, 20, 60),
            )
        )
        self.register(
            ResearchFactor(
                name="macd_hist",
                category="trend",
                description="MACD 柱",
                higher_is_better=True,
                required_columns=["close"],
                min_periods=26,
                compute=lambda df: self._core_registry.get("macd_hist").compute(df),
            )
        )
        self.register(
            ResearchFactor(
                name="volatility_20d",
                category="volatility",
                description="20 日波动率",
                higher_is_better=False,
                required_columns=["close"],
                min_periods=20,
                compute=lambda df: pd.to_numeric(df["close"], errors="coerce").pct_change().rolling(20, min_periods=20).std(),
            )
        )
        self.register(
            ResearchFactor(
                name="atr_pct_14",
                category="volatility",
                description="ATR/Close",
                higher_is_better=False,
                required_columns=["high", "low", "close"],
                min_periods=14,
                compute=lambda df: self._core_registry.get("atr_value").compute(df) / pd.to_numeric(df["close"], errors="coerce"),
            )
        )
        self.register(
            ResearchFactor(
                name="max_drawdown_20d",
                category="volatility",
                description="20 日滚动最大回撤",
                higher_is_better=False,
                required_columns=["close"],
                min_periods=20,
                compute=lambda df: self._rolling_max_drawdown(df, 20),
            )
        )
        self.register(
            ResearchFactor(
                name="volume_ratio_20d",
                category="volume_price",
                description="量比 20 日",
                higher_is_better=True,
                required_columns=["volume"],
                min_periods=20,
                compute=lambda df: pd.to_numeric(df["volume"], errors="coerce") / pd.to_numeric(df["volume"], errors="coerce").rolling(20, min_periods=20).mean(),
            )
        )
        self.register(
            ResearchFactor(
                name="turnover_proxy_20d",
                category="volume_price",
                description="成交额代理 20 日均值",
                higher_is_better=True,
                required_columns=["amount", "volume", "close"],
                min_periods=20,
                compute=lambda df: self._turnover_proxy(df),
            )
        )
        self.register(
            ResearchFactor(
                name="pe_ttm",
                category="valuation",
                description="PE_TTM",
                higher_is_better=False,
                required_columns=[],
                min_periods=0,
                compute=lambda df: self._core_registry.get("pe_ttm").compute(df),
            )
        )
        self.register(
            ResearchFactor(
                name="pb",
                category="valuation",
                description="PB",
                higher_is_better=False,
                required_columns=[],
                min_periods=0,
                compute=lambda df: self._core_registry.get("pb").compute(df),
            )
        )
        self.register(
            ResearchFactor(
                name="dividend_yield",
                category="valuation",
                description="股息率",
                higher_is_better=True,
                required_columns=[],
                min_periods=0,
                compute=lambda df: self._core_registry.get("dividend_yield").compute(df),
            )
        )

    @staticmethod
    def _ratio_of_rolling_means(df: pd.DataFrame, fast: int, slow: int) -> pd.Series:
        close = pd.to_numeric(df["close"], errors="coerce")
        fast_ma = close.rolling(fast, min_periods=fast).mean()
        slow_ma = close.rolling(slow, min_periods=slow).mean().replace(0, pd.NA)
        return fast_ma / slow_ma - 1

    @staticmethod
    def _rolling_max_drawdown(df: pd.DataFrame, window: int) -> pd.Series:
        close = pd.to_numeric(df["close"], errors="coerce")
        rolling_peak = close.rolling(window, min_periods=window).max()
        return close / rolling_peak - 1

    @staticmethod
    def _turnover_proxy(df: pd.DataFrame) -> pd.Series:
        if "amount" in df.columns:
            base = pd.to_numeric(df["amount"], errors="coerce")
        else:
            base = pd.to_numeric(df["close"], errors="coerce") * pd.to_numeric(df["volume"], errors="coerce")
        return base.rolling(20, min_periods=20).mean()


def get_research_factor_library() -> ResearchFactorLibrary:
    return ResearchFactorLibrary()
