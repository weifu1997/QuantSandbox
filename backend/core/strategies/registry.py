from __future__ import annotations

from collections.abc import Callable
from typing import Type

from backend.core.strategy import Strategy
from .target_weight_demo import TargetWeightDemoStrategy
from .multi_factor_target_weight import MultiFactorTargetWeightStrategy


class StrategyRegistry:
    def __init__(self):
        self._strategies: dict[str, Type[Strategy]] = {}

    def register(self, strategy_cls: Type[Strategy]) -> None:
        self._strategies[strategy_cls.name] = strategy_cls

    def get(self, name: str) -> Type[Strategy]:
        if name not in self._strategies:
            raise KeyError(f"未知的新策略名称: {name}")
        return self._strategies[name]

    def create(self, name: str, params: dict | None = None) -> Strategy:
        strategy_cls = self.get(name)
        return strategy_cls(params or {})

    def list_meta(self) -> list[dict]:
        metas = []
        for strategy_cls in self._strategies.values():
            metas.append(strategy_cls().meta())
        return metas


def get_strategy_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(MultiFactorTargetWeightStrategy)  # 默认策略（第一个注册）
    registry.register(TargetWeightDemoStrategy)          # SMOKE ONLY：保留供回归验证
    return registry
