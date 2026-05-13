from __future__ import annotations

from dataclasses import dataclass, field
from math import floor
from typing import Any, Literal

from backend.core.strategy import PositionTarget


@dataclass(slots=True)
class CurrentPosition:
    """当前持仓快照：供仓位管理器比较目标权重与现状。"""

    symbol: str
    shares: int = 0
    market_value: float = 0.0
    weight: float = 0.0
    last_price: float = 0.0


@dataclass(slots=True)
class Order:
    """最小交易指令骨架。"""

    symbol: str
    action: Literal["buy", "sell", "hold"]
    target_weight: float
    current_weight: float = 0.0
    delta_weight: float = 0.0
    reason: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "target_weight": self.target_weight,
            "current_weight": self.current_weight,
            "delta_weight": self.delta_weight,
            "reason": self.reason,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


class PositionManager:
    """仓位管理器骨架：先定义契约，后续再接真实执行与撮合。"""

    def __init__(self, max_position_weight: float = 0.30, max_total_exposure: float = 0.95, lot_size: int = 100):
        self.max_position_weight = max_position_weight
        self.max_total_exposure = max_total_exposure
        self.lot_size = lot_size

    def constraints(self) -> dict[str, float | int]:
        return {
            "max_position_weight": self.max_position_weight,
            "max_total_exposure": self.max_total_exposure,
            "lot_size": self.lot_size,
        }

    def _round_down_to_lot(self, shares: float) -> int:
        if shares <= 0:
            return 0
        return int(floor(shares / self.lot_size) * self.lot_size)

    def allocate(
        self,
        targets: list[PositionTarget],
        current_positions: list[CurrentPosition],
        available_cash: float,
        total_equity: float,
    ) -> list[Order]:
        """根据目标仓位与当前持仓生成最小指令骨架。

        当前版本增强：
        - 单票目标先裁剪到单票上限
        - 总目标仓位超过 max_total_exposure 时按比例缩放
        - 先卖后买
        - 买入指令按 confidence 从高到低排序
        - A 股 100 股整手约束
        - 基于 available_cash 做逐单资金分配
        """
        current_map = {position.symbol: position for position in current_positions}
        constrained_targets: list[PositionTarget] = []

        for target in targets:
            capped_target_weight = min(max(float(target.target_weight), 0.0), self.max_position_weight)
            constrained_targets.append(
                PositionTarget(
                    symbol=target.symbol,
                    target_weight=capped_target_weight,
                    confidence=float(target.confidence),
                    metadata=dict(target.metadata or {}),
                )
            )

        total_target_weight = sum(target.target_weight for target in constrained_targets)
        scale = 1.0
        if total_target_weight > self.max_total_exposure > 0:
            scale = self.max_total_exposure / total_target_weight
            constrained_targets = [
                PositionTarget(
                    symbol=target.symbol,
                    target_weight=target.target_weight * scale,
                    confidence=target.confidence,
                    metadata=dict(target.metadata or {}),
                )
                for target in constrained_targets
            ]

        raw_orders: list[Order] = []
        for target in constrained_targets:
            current = current_map.get(target.symbol)
            current_weight = float(current.weight) if current else 0.0
            delta_weight = target.target_weight - current_weight
            price = float(current.last_price) if current and current.last_price > 0 else float(target.metadata.get("last_price", 0.0) or 0.0)

            if delta_weight > 0:
                action: Literal["buy", "sell", "hold"] = "buy"
                reason = "target_above_current"
            elif delta_weight < 0:
                action = "sell"
                reason = "target_below_current"
            else:
                action = "hold"
                reason = "target_equals_current"

            raw_orders.append(
                Order(
                    symbol=target.symbol,
                    action=action,
                    target_weight=target.target_weight,
                    current_weight=current_weight,
                    delta_weight=delta_weight,
                    reason=reason,
                    confidence=float(target.confidence),
                    metadata={
                        "available_cash": available_cash,
                        "total_equity": total_equity,
                        "constraints": self.constraints(),
                        "target_scale": scale,
                        "reference_price": price,
                        **dict(target.metadata or {}),
                    },
                )
            )

        sells = [order for order in raw_orders if order.action == "sell"]
        holds = [order for order in raw_orders if order.action == "hold"]
        buys = [order for order in raw_orders if order.action == "buy"]
        buys.sort(key=lambda order: (-order.confidence, -order.delta_weight, order.symbol))
        sells.sort(key=lambda order: (order.delta_weight, order.symbol))
        holds.sort(key=lambda order: order.symbol)

        cash_budget = max(float(available_cash), 0.0)

        for order in sells:
            price = float(order.metadata.get("reference_price", 0.0) or 0.0)
            current = current_map.get(order.symbol)
            current_shares = int(current.shares) if current else 0
            current_value = float(current.market_value) if current else 0.0
            planned_sell_value = abs(order.delta_weight) * float(total_equity)
            planned_sell_shares = self._round_down_to_lot(planned_sell_value / price) if price > 0 else 0
            executed_sell_shares = min(current_shares, planned_sell_shares) if current_shares > 0 else planned_sell_shares
            executed_sell_value = executed_sell_shares * price if price > 0 else min(planned_sell_value, current_value)
            if executed_sell_shares == 0 and planned_sell_value > 0:
                order.reason = "sell_lot_too_small_or_price_missing"
                order.action = "hold"
            cash_budget += max(executed_sell_value, 0.0)
            order.metadata.update({
                "planned_trade_value": planned_sell_value,
                "planned_shares": planned_sell_shares,
                "executed_shares": executed_sell_shares,
                "executed_trade_value": executed_sell_value,
                "cash_budget_after": cash_budget,
            })

        for order in buys:
            price = float(order.metadata.get("reference_price", 0.0) or 0.0)
            planned_buy_value = max(order.delta_weight, 0.0) * float(total_equity)
            if price <= 0:
                order.action = "hold"
                order.reason = "buy_skipped_missing_price"
                order.metadata.update({
                    "planned_trade_value": planned_buy_value,
                    "planned_shares": 0,
                    "executed_shares": 0,
                    "executed_trade_value": 0.0,
                    "cash_budget_after": cash_budget,
                    "adjustment_reason": "missing_price",
                })
                continue

            planned_shares = self._round_down_to_lot(planned_buy_value / price)
            affordable_shares = self._round_down_to_lot(cash_budget / price)
            executed_shares = min(planned_shares, affordable_shares)
            executed_value = executed_shares * price

            if planned_shares == 0:
                order.action = "hold"
                order.reason = "buy_skipped_lot_too_small"
                adjustment_reason = "lot_too_small"
            elif affordable_shares == 0:
                order.action = "hold"
                order.reason = "buy_skipped_insufficient_cash"
                adjustment_reason = "insufficient_cash"
            elif executed_shares < planned_shares:
                order.reason = "buy_trimmed_by_cash"
                adjustment_reason = "trimmed_by_cash"
            else:
                adjustment_reason = "fully_allocated"

            cash_budget -= executed_value
            order.metadata.update({
                "planned_trade_value": planned_buy_value,
                "planned_shares": planned_shares,
                "executed_shares": executed_shares,
                "executed_trade_value": executed_value,
                "cash_budget_after": cash_budget,
                "adjustment_reason": adjustment_reason,
            })

        return sells + buys + holds
