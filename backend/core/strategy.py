from __future__ import annotations

import pandas as pd

from backend.core.strategy_common import board_limit_ratio
from backend.core.strategies.dual_ma import DualMaStrategy
from backend.core.strategies.bollinger_bands import BollingerBandsStrategy
from backend.core.strategies.rsi_reversal import RsiReversalStrategy


class StrategyFactory:
    """量化策略工厂：只负责路由与公共字段补齐。"""

    @staticmethod
    def generate_signals(df: pd.DataFrame, strategy_name: str, params: dict) -> pd.DataFrame:
        df = df.copy()
        df["trade_signal"] = 0

        if strategy_name == "dual_ma":
            result = DualMaStrategy.generate(df, params)
        elif strategy_name == "bollinger_bands":
            result = BollingerBandsStrategy.generate(df, params)
        elif strategy_name == "rsi_reversal":
            result = RsiReversalStrategy.generate(df, params)
        else:
            raise ValueError(f"未知的策略名称: {strategy_name}")

        if "symbol" not in result.columns and "ts_code" in result.columns:
            result["symbol"] = result["ts_code"]
        if "name" not in result.columns:
            result["name"] = ""
        if "list_date" not in result.columns:
            result["list_date"] = ""
        if "delist_date" not in result.columns:
            result["delist_date"] = ""
        if "limit_ratio" not in result.columns:
            result["limit_ratio"] = result.apply(
                lambda row: board_limit_ratio(
                    row.get("symbol", ""),
                    row.get("name", ""),
                    row.get("list_date", ""),
                    row.get("delist_date", ""),
                    str(row.get("date", ""))[:10],
                ),
                axis=1,
            )
        return result
