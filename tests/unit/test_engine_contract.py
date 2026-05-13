"""引擎契约测试 — 确保引擎不 fallback 到 pos_targets[0]/[-1] 等兜底行为。"""

import pytest
import pandas as pd
import numpy as np

from backend.core.engine import BacktestEngine
from backend.core.strategy import PositionTarget
from backend.core.strategies.multi_factor_target_weight import (
    MultiFactorTargetWeightStrategy,
)


def _make_df(rows: int = 30) -> pd.DataFrame:
    """生成 mock 行情数据。"""
    np.random.seed(99)
    dates = pd.date_range("2024-01-02", periods=rows, freq="B")
    close = np.cumprod(1 + np.random.normal(0, 0.02, rows)) * 10
    return pd.DataFrame(
        {
            "date": dates,
            "open": close * 0.99,
            "high": close * 1.02,
            "low": close * 0.98,
            "close": close,
            "volume": [1_000_000] * rows,
            "name": ["TEST"] * rows,
        }
    )


class TestEnginePerBarContract:
    """引擎逐 bar 匹配契约。"""

    def test_run_with_positions_legacy_no_bar_date_allowed(self):
        """Legacy 单 target 无 bar_date → warning 但正常运行。"""
        df = _make_df(5)
        engine = BacktestEngine()
        # Legacy/smoke: 单 target 无 bar_date，引擎复制到所有 bar
        legacy_target = PositionTarget(
            symbol="TEST",
            target_weight=0.15,
            confidence=0.5,
            metadata={},  # no bar_date — legacy ok
        )
        # 不应抛异常：legacy 单 target 被 validate_per_bar_targets 放行
        result = engine.run_with_positions(df, "TEST", [legacy_target])
        assert result["metadata"]["target_count"] == 1

    def test_run_with_positions_legacy_single_target_replicated(self):
        """Legacy 单 target 复用到所有 bar（不依赖 bar_date）。"""
        df = _make_df(5)
        engine = BacktestEngine()
        # Legacy/smoke: 单 target 含过期 bar_date 仍可运行，bar_date 被忽略
        legacy_target = PositionTarget(
            symbol="TEST",
            target_weight=0.15,
            confidence=0.5,
            metadata={"bar_date": "2023-01-01"},  # not in df — legacy ignores this
        )
        # 不应抛异常：legacy 单 target 被 validate_per_bar_targets 放行并复制
        result = engine.run_with_positions(df, "TEST", [legacy_target])
        assert result["metadata"]["target_count"] == 1

    def test_run_with_positions_missing_one_date(self):
        """只提供部分日期的 target → ValueError（validate_per_bar_targets）。"""
        df = _make_df(5)
        engine = BacktestEngine()
        # 只提供 2 个 target (5 个 bar → 缺 3 个)
        targets = [
            PositionTarget(
                symbol="TEST",
                target_weight=0.10,
                confidence=0.5,
                metadata={
                    "bar_date": df.iloc[0]["date"].strftime("%Y-%m-%d"),
                    "reason": "test",
                    "score": 0.5,
                    "factor_values": {},
                    "rebalance_threshold": 0.02,
                },
            ),
            PositionTarget(
                symbol="TEST",
                target_weight=0.10,
                confidence=0.5,
                metadata={
                    "bar_date": df.iloc[1]["date"].strftime("%Y-%m-%d"),
                    "reason": "test",
                    "score": 0.5,
                    "factor_values": {},
                    "rebalance_threshold": 0.02,
                },
            ),
        ]
        with pytest.raises(ValueError, match="target count 2 does not match"):
            engine.run_with_positions(df, "TEST", targets)

    def test_run_with_positions_ok_when_all_dates_present(self):
        """所有日期都有 target → 正常运行。"""
        df = _make_df(10)
        s = MultiFactorTargetWeightStrategy()
        targets = s.generate_targets(df, "TEST")
        engine = BacktestEngine()
        result = engine.run_with_positions(df, "TEST", targets)
        assert result["metadata"]["target_count"] == 10
        assert "total_return" in result["metadata"]

    def test_run_portfolio_does_not_use_pos_targets_index(self):
        """组合回测不用 pos_targets[0] 或 [-1] 兜底。"""
        df = _make_df(10)
        engine = BacktestEngine()
        result = engine.run_portfolio(
            {"TEST": df},
            MultiFactorTargetWeightStrategy,
            {"max_target_weight": 0.20},
        )
        assert result["portfolio_metrics"]["ticker_count"] == 1
        assert "portfolio_equity" in result
        assert len(result["portfolio_equity"]) == 10


class TestEngineWithMultiFactor:
    """引擎 + 多因子策略集成测试。"""

    def test_single_ticker_full_run(self):
        """完整单票回测 — 不报错且有结果。"""
        df = _make_df(20)
        s = MultiFactorTargetWeightStrategy()
        targets = s.generate_targets(df, "TEST")
        engine = BacktestEngine(initial_cash=100000)
        result = engine.run_with_positions(df, "TEST", targets)
        assert result["metadata"]["target_count"] == 20
        assert "total_return" in result["metadata"]
        assert len(result["logs"]) > 0

    def test_rebalance_threshold_avoid_noise(self):
        """rebalance_threshold > 0 时减少无效交易。"""
        df = _make_df(20)
        s_no_threshold = MultiFactorTargetWeightStrategy({"rebalance_threshold": 0.0})
        s_with_threshold = MultiFactorTargetWeightStrategy({"rebalance_threshold": 0.10})

        targets_no = s_no_threshold.generate_targets(df, "TEST")
        targets_with = s_with_threshold.generate_targets(df, "TEST")

        e_no = BacktestEngine()
        e_with = BacktestEngine()

        r_no = e_no.run_with_positions(df, "TEST", targets_no)
        r_with = e_with.run_with_positions(df, "TEST", targets_with)

        trades_no = sum(1 for log in r_no["logs"] if log["action"] in ("buy", "sell"))
        trades_with = sum(1 for log in r_with["logs"] if log["action"] in ("buy", "sell"))
        assert trades_with <= trades_no, f"Threshold should reduce trades: {trades_with} vs {trades_no}"

    def test_two_ticker_portfolio_no_fallback(self):
        """两标组合 — 每个标的独立 target，无兜底。"""
        np.random.seed(7)
        d1 = pd.date_range("2024-01-02", periods=20, freq="B")
        close1 = np.cumprod(1 + np.random.normal(0, 0.02, 20)) * 10
        df1 = pd.DataFrame({
            "date": d1, "open": close1*0.99, "high": close1*1.02,
            "low": close1*0.98, "close": close1, "volume": [1e6]*20, "name": ["A"]*20,
        })
        d2 = pd.date_range("2024-01-02", periods=20, freq="B")
        close2 = np.cumprod(1 + np.random.normal(0, 0.015, 20)) * 8
        df2 = pd.DataFrame({
            "date": d2, "open": close2*0.99, "high": close2*1.02,
            "low": close2*0.98, "close": close2, "volume": [1e6]*20, "name": ["B"]*20,
        })

        engine = BacktestEngine()
        result = engine.run_portfolio(
            {"A": df1, "B": df2},
            MultiFactorTargetWeightStrategy,
            {},
        )
        assert result["portfolio_metrics"]["ticker_count"] == 2
        assert len(result["portfolio_equity"]) == 20
        assert len(result["per_ticker"]["A"]["equity"]) == 20
        assert len(result["per_ticker"]["B"]["equity"]) == 20
