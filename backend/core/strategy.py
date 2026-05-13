from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(slots=True)
class PositionTarget:
    """多因子/仓位管理路径的目标仓位契约。"""

    symbol: str
    target_weight: float
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def bar_date(self) -> str | None:
        """从 metadata 提取 bar_date，供引擎侧直接使用。"""
        return self.metadata.get("bar_date")

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "target_weight": self.target_weight,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


class Strategy(ABC):
    """新策略层基类：依赖因子、参数与目标仓位输出。"""

    name: str = "base_strategy"
    description: str = ""
    factor_names: list[str] = []
    parameter_schema: dict[str, Any] = {}

    def __init__(self, params: dict[str, Any] | None = None):
        self.params = params or {}

    def meta(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "factor_names": list(self.factor_names),
            "parameter_schema": dict(self.parameter_schema),
        }

    @abstractmethod
    def generate_targets(self, df: pd.DataFrame, symbol: str) -> list[PositionTarget]:
        """基于行情与因子结果输出绝对目标权重。"""