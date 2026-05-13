from __future__ import annotations

import pandas as pd

from backend.core.factors import get_factor_registry
from backend.core.strategy import PositionTarget, Strategy


class TargetWeightDemoStrategy(Strategy):
    """SMOKE ONLY：最小目标仓位示例策略，用于回归验证。"""

    name = "target_weight_demo"
    description = "SMOKE ONLY：根据 RSI 连续值生成 0-30% 目标仓位的最小示例策略"
    factor_names = ["rsi_value"]
    parameter_schema = {
        "rsi_period": {"type": "integer", "default": 14, "minimum": 2},
        "max_target_weight": {"type": "number", "default": 0.30, "minimum": 0.0, "maximum": 1.0},
        "oversold_floor": {"type": "number", "default": 30.0, "minimum": 0.0, "maximum": 100.0},
        "overbought_ceiling": {"type": "number", "default": 70.0, "minimum": 0.0, "maximum": 100.0},
        "rebalance_threshold": {"type": "number", "default": 0.03, "minimum": 0.0, "maximum": 1.0},
    }

    def generate_targets(self, df: pd.DataFrame, symbol: str) -> list[PositionTarget]:
        """为每根 bar 生成当日目标仓位。

        旧实现只返回最后一天的目标仓位，单票回测会把它误当成整段历史
        的默认仓位，导致日志表现为“先买到 30%，后续每天 100 股再平衡”。
        这里改为逐日输出带 `bar_date` 的 target，避免未来函数和静态仓位误用。
        """
        if df.empty:
            return [PositionTarget(symbol=symbol, target_weight=0.0, confidence=0.0, metadata={"reason": "empty_dataframe"})]

        period = int(self.params.get("rsi_period", 14))
        max_target_weight = float(self.params.get("max_target_weight", 0.30))
        oversold_floor = float(self.params.get("oversold_floor", 30.0))
        overbought_ceiling = float(self.params.get("overbought_ceiling", 70.0))
        rebalance_threshold = float(self.params.get("rebalance_threshold", 0.03))

        registry = get_factor_registry()
        rsi_factor = registry.get("rsi_value")
        if hasattr(rsi_factor, "period"):
            rsi_factor.period = period
            rsi_factor.params_schema["period"]["default"] = period

        rsi_series = rsi_factor.compute(df)
        band = max(overbought_ceiling - oversold_floor, 1e-9)
        targets: list[PositionTarget] = []

        for idx, row in df.iterrows():
            raw_date = row.get("date")
            bar_date = raw_date.strftime("%Y-%m-%d") if hasattr(raw_date, "strftime") else str(raw_date or "")
            latest_rsi = rsi_series.loc[idx]

            if pd.isna(latest_rsi):
                target_weight = 0.0
                confidence = 0.0
                reason = "rsi_unavailable"
                latest_rsi_value = None
            else:
                latest_rsi_value = float(latest_rsi)
                if latest_rsi_value <= oversold_floor:
                    target_weight = max_target_weight
                elif latest_rsi_value >= overbought_ceiling:
                    target_weight = 0.0
                else:
                    normalized = (overbought_ceiling - latest_rsi_value) / band
                    target_weight = max_target_weight * max(0.0, min(1.0, normalized))
                confidence = min(abs(50.0 - latest_rsi_value) / 50.0, 1.0)
                reason = "rsi_target_weight"

            metadata = {
                "strategy": self.name,
                "factor": "rsi_value",
                "rsi_period": period,
                "rebalance_threshold": rebalance_threshold,
                "reason": reason,
                "bar_date": bar_date,
            }
            if latest_rsi_value is not None:
                metadata["latest_rsi"] = round(latest_rsi_value, 6)

            targets.append(
                PositionTarget(
                    symbol=symbol,
                    target_weight=round(float(target_weight), 6),
                    confidence=round(float(confidence), 6),
                    metadata=metadata,
                )
            )

        return targets
