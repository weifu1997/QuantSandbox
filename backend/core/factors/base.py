from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(slots=True)
class Factor(ABC):
    """连续值因子基类。"""

    name: str
    category: str
    description: str = ""
    params_schema: dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.Series:
        """基于行情数据输出连续值因子。"""

    def meta(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "params_schema": self.params_schema,
        }

    def validate_input(self, df: pd.DataFrame, required_columns: list[str]) -> None:
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise ValueError(f"因子 {self.name} 缺少必需列: {', '.join(missing)}")
