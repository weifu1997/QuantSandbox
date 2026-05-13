from __future__ import annotations

import pandas as pd

from .base import Factor


class BollingerPosition(Factor):
    def __init__(self, window: int = 20, std_dev: float = 2.0):
        super().__init__(
            name="bollinger_position",
            category="technical",
            description="价格在布林带中的相对位置，0=下轨，1=上轨",
            params_schema={
                "window": {"type": "integer", "default": window, "minimum": 2},
                "std_dev": {"type": "number", "default": std_dev, "exclusiveMinimum": 0},
            },
        )
        self.window = window
        self.std_dev = std_dev

    def compute(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, ["close"])
        close = pd.to_numeric(df["close"], errors="coerce")
        mid = close.rolling(self.window, min_periods=self.window).mean()
        vol = close.rolling(self.window, min_periods=self.window).std()
        upper = mid + self.std_dev * vol
        lower = mid - self.std_dev * vol
        width = (upper - lower).replace(0, pd.NA)
        series = ((close - lower) / width).clip(lower=0, upper=1)
        return series.rename(self.name)


class MaCrossValue(Factor):
    def __init__(self, fast: int = 5, slow: int = 20):
        super().__init__(
            name="ma_cross_value",
            category="technical",
            description="快均线相对慢均线的偏离比例",
            params_schema={
                "fast": {"type": "integer", "default": fast, "minimum": 1},
                "slow": {"type": "integer", "default": slow, "minimum": 2},
            },
        )
        self.fast = fast
        self.slow = slow

    def compute(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, ["close"])
        close = pd.to_numeric(df["close"], errors="coerce")
        fast_ma = close.rolling(self.fast, min_periods=self.fast).mean()
        slow_ma = close.rolling(self.slow, min_periods=self.slow).mean().replace(0, pd.NA)
        return ((fast_ma - slow_ma) / slow_ma).rename(self.name)


class RsiValue(Factor):
    def __init__(self, period: int = 14):
        super().__init__(
            name="rsi_value",
            category="technical",
            description="标准 RSI 值，范围 0-100",
            params_schema={
                "period": {"type": "integer", "default": period, "minimum": 2},
            },
        )
        self.period = period

    def compute(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, ["close"])
        close = pd.to_numeric(df["close"], errors="coerce")
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(self.period, min_periods=self.period).mean()
        avg_loss = loss.rolling(self.period, min_periods=self.period).mean().replace(0, pd.NA)
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.rename(self.name)


class MacdHist(Factor):
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        super().__init__(
            name="macd_hist",
            category="technical",
            description="MACD 柱值（DIFF - DEA）",
            params_schema={
                "fast": {"type": "integer", "default": fast, "minimum": 1},
                "slow": {"type": "integer", "default": slow, "minimum": 2},
                "signal": {"type": "integer", "default": signal, "minimum": 1},
            },
        )
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def compute(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, ["close"])
        close = pd.to_numeric(df["close"], errors="coerce")
        fast_ema = close.ewm(span=self.fast, adjust=False).mean()
        slow_ema = close.ewm(span=self.slow, adjust=False).mean()
        diff = fast_ema - slow_ema
        dea = diff.ewm(span=self.signal, adjust=False).mean()
        return (diff - dea).rename(self.name)


class AtrValue(Factor):
    def __init__(self, period: int = 14):
        super().__init__(
            name="atr_value",
            category="technical",
            description="平均真实波幅 ATR",
            params_schema={
                "period": {"type": "integer", "default": period, "minimum": 2},
            },
        )
        self.period = period

    def compute(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, ["high", "low", "close"])
        high = pd.to_numeric(df["high"], errors="coerce")
        low = pd.to_numeric(df["low"], errors="coerce")
        close = pd.to_numeric(df["close"], errors="coerce")
        prev_close = close.shift(1)
        true_range = pd.concat([
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        return true_range.rolling(self.period, min_periods=self.period).mean().rename(self.name)
