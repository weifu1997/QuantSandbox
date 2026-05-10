from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.workflows.low_value_flow.rules import safe_float


@dataclass
class StopLossResult:
    stop_loss_price: float | None
    reference_low_price: float | None
    price_based_stop_loss: float | None


class StopLossCalculator:
    def calculate(self, data: dict[str, Any]) -> StopLossResult:
        buy_price = safe_float(data.get('buy_price') or data.get('latest_price'))
        prior_low = safe_float(data.get('prior_low_price') or data.get('support_price'))
        low_based = prior_low * 0.97 if prior_low is not None and prior_low > 0 else None
        price_based = buy_price * 0.92 if buy_price is not None and buy_price > 0 else None
        candidates = [value for value in [low_based, price_based] if value is not None]
        stop = max(candidates) if candidates else None
        if stop is not None:
            stop = round(stop, 3)
        return StopLossResult(
            stop_loss_price=stop,
            reference_low_price=round(low_based, 3) if low_based is not None else None,
            price_based_stop_loss=round(price_based, 3) if price_based is not None else None,
        )
