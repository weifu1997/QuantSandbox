from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .base import Factor
from .fundamental import DividendYield, Pb, PeTtm
from .technical import AtrValue, BollingerPosition, MaCrossValue, MacdHist, RsiValue


class FactorRegistry:
    def __init__(self, factors: Iterable[Factor] | None = None):
        self._factors: dict[str, Factor] = {}
        if factors:
            for factor in factors:
                self.register(factor)

    def register(self, factor: Factor) -> None:
        self._factors[factor.name] = factor

    def get(self, name: str) -> Factor:
        if name not in self._factors:
            raise KeyError(f"未知因子: {name}")
        return self._factors[name]

    def list_meta(self) -> list[dict[str, Any]]:
        return [factor.meta() for factor in self._factors.values()]


def get_factor_registry() -> FactorRegistry:
    return FactorRegistry(
        factors=[
            BollingerPosition(),
            MaCrossValue(),
            RsiValue(),
            MacdHist(),
            AtrValue(),
            PeTtm(),
            Pb(),
            DividendYield(),
        ]
    )
