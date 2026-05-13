"""多因子策略行为测试 — 确保 multi_factor_target_weight 符合契约。"""

import pytest
import pandas as pd
import numpy as np

from backend.core.strategies.multi_factor_target_weight import (
    MultiFactorTargetWeightStrategy,
    _score_pe,
    _score_pb,
    _score_ma_cross,
    _score_macd_hist,
    _score_rsi,
    _score_atr,
)


def _make_df(rows: int = 30, with_fundamentals: bool = True) -> pd.DataFrame:
    """生成 mock 行情数据。"""
    np.random.seed(42)
    dates = pd.date_range("2024-01-02", periods=rows, freq="B")
    close = np.cumprod(1 + np.random.normal(0, 0.02, rows)) * 10
    data = {
        "date": dates,
        "open": close * 0.99,
        "high": close * 1.02,
        "low": close * 0.98,
        "close": close,
        "volume": [1_000_000] * rows,
        "name": ["TEST"] * rows,
    }
    if with_fundamentals:
        data["pe_ttm"] = [15.0 + np.random.random() * 30 for _ in range(rows)]
        data["pb"] = [1.5 + np.random.random() * 3 for _ in range(rows)]
    return pd.DataFrame(data)


class TestMultiFactorStrategyContract:
    """策略契约测试。"""

    def test_per_bar_output_length_matches_df(self):
        """30 bar df → 30 targets。"""
        df = _make_df(30)
        s = MultiFactorTargetWeightStrategy()
        targets = s.generate_targets(df, "TEST")
        assert len(targets) == 30

    def test_empty_df_returns_single_target(self):
        """空 df → 一个零仓位 target。"""
        df = _make_df(0)
        s = MultiFactorTargetWeightStrategy()
        targets = s.generate_targets(df, "TEST")
        assert len(targets) == 1
        assert targets[0].target_weight == 0.0

    def test_all_targets_have_bar_date(self):
        """每个 target 有 bar_date。"""
        df = _make_df(30)
        s = MultiFactorTargetWeightStrategy()
        targets = s.generate_targets(df, "TEST")
        assert all(t.bar_date is not None and t.bar_date != "" for t in targets)

    def test_all_targets_have_reason(self):
        """每个 target 有 reason。"""
        df = _make_df(30)
        s = MultiFactorTargetWeightStrategy()
        targets = s.generate_targets(df, "TEST")
        assert all("reason" in t.metadata for t in targets)

    def test_all_targets_have_score(self):
        """每个 target 有 score。"""
        df = _make_df(30)
        s = MultiFactorTargetWeightStrategy()
        targets = s.generate_targets(df, "TEST")
        assert all("score" in t.metadata for t in targets)

    def test_all_targets_have_factor_values(self):
        """每个 target 有 factor_values 含 5 个子因子。"""
        df = _make_df(30)
        s = MultiFactorTargetWeightStrategy()
        targets = s.generate_targets(df, "TEST")
        for t in targets:
            fv = t.metadata["factor_values"]
            assert "valuation" in fv
            assert "trend" in fv
            assert "momentum" in fv
            assert "reversal" in fv
            assert "volatility" in fv

    def test_target_weight_in_range(self):
        """所有 target_weight ∈ [0, max_target_weight]。"""
        df = _make_df(30)
        s = MultiFactorTargetWeightStrategy({"max_target_weight": 0.25})
        targets = s.generate_targets(df, "TEST")
        assert all(0.0 <= t.target_weight <= 0.25 for t in targets)

    def test_score_in_range(self):
        """所有 score ∈ [0, 1]。"""
        df = _make_df(30)
        s = MultiFactorTargetWeightStrategy()
        targets = s.generate_targets(df, "TEST")
        scores = [t.metadata["score"] for t in targets]
        assert all(0.0 <= s <= 1.0 for s in scores)

    def test_target_weight_varies(self):
        """至少在有信号的样本中 target_weight 有变化。"""
        df = _make_df(30)
        s = MultiFactorTargetWeightStrategy()
        targets = s.generate_targets(df, "TEST")
        weights = [t.target_weight for t in targets]
        unique = len(set(weights))
        assert unique > 1, f"Expected >1 unique weights, got {unique}"

    def test_no_fundamentals_does_not_error(self):
        """PE/PB 列缺失 → 不报错。"""
        df = _make_df(30, with_fundamentals=False)
        s = MultiFactorTargetWeightStrategy()
        targets = s.generate_targets(df, "TEST")
        assert len(targets) == 30  # should still produce per-bar targets

    def test_rebalance_threshold_present(self):
        """每个 target metadata 含 rebalance_threshold。"""
        df = _make_df(30)
        s = MultiFactorTargetWeightStrategy({"rebalance_threshold": 0.05})
        targets = s.generate_targets(df, "TEST")
        assert all(t.metadata.get("rebalance_threshold") == 0.05 for t in targets)


class TestScoringFunctions:
    """因子打分函数测试。"""

    def test_score_pe_low_is_high(self):
        assert _score_pe(10.0, {}) > 0.8

    def test_score_pe_none_is_neutral(self):
        assert _score_pe(None, {}) == 0.50

    def test_score_pe_very_high_is_zero(self):
        assert _score_pe(500.0, {}) == 0.0

    def test_score_pb_low_is_high(self):
        assert _score_pb(0.8, {}) == 1.0

    def test_score_pb_none_is_neutral(self):
        assert _score_pb(None, {}) == 0.50

    def test_score_ma_cross_positive_is_high(self):
        assert _score_ma_cross(0.06) == 1.0

    def test_score_ma_cross_negative_is_low(self):
        assert _score_ma_cross(-0.06) == 0.0

    def test_score_macd_hist_positive_is_high(self):
        assert _score_macd_hist(1.5) == 1.0

    def test_score_macd_hist_none_is_neutral(self):
        assert _score_macd_hist(None) == 0.50

    def test_score_rsi_very_low_is_high(self):
        """RSI < 25 → 高反转概率 → 高分。"""
        assert _score_rsi(20.0) == 0.90

    def test_score_rsi_very_high_is_low(self):
        """RSI > 85 → 深度超买 → 0 分。"""
        assert _score_rsi(90.0) == 0.0

    def test_score_atr_high_is_low(self):
        """高波动 → 降分。"""
        assert _score_atr(0.06) == 0.0

    def test_score_atr_none_is_neutral(self):
        assert _score_atr(None) == 0.50
