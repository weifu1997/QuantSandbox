"""策略契约单元测试 — 确保所有正式策略必须输出逐 bar target。"""

import pytest
import pandas as pd

from backend.core.strategy import PositionTarget, Strategy
from backend.core.strategy_contract import (
    validate_per_bar_targets,
    LEGACY_SINGLE_TARGET_WARNING,
)


def _make_targets(count: int, symbol: str = "TEST") -> list[PositionTarget]:
    """生成带 bar_date 的 targets 列表。"""
    targets = []
    for i in range(count):
        targets.append(PositionTarget(
            symbol=symbol,
            target_weight=0.1,
            confidence=0.5,
            metadata={"bar_date": f"2024-01-{i+2:02d}", "reason": "test", "score": 0.5},
        ))
    return targets


def _make_df(rows: int) -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.date_range("2024-01-02", periods=rows, freq="B"),
        "open": [10.0] * rows,
        "close": [10.0] * rows,
        "high": [10.5] * rows,
        "low": [9.5] * rows,
        "volume": [1000] * rows,
    })


class TestValidatePerBarTargets:
    """validate_per_bar_targets 契约验证。"""

    def test_exact_match_passes(self):
        """target 数量 == df 长度：通过。"""
        targets = _make_targets(5)
        result = validate_per_bar_targets(targets, 5, "test_strat", "TEST")
        assert result is targets  # 返回原始列表

    def test_length_mismatch_raises(self):
        """target 数量 != df 长度：抛 ValueError。"""
        targets = _make_targets(3)
        with pytest.raises(ValueError, match="target count 3 does not match"):
            validate_per_bar_targets(targets, 5, "test_strat", "TEST")

    def test_single_target_multi_bar_warns(self, caplog):
        """单 target 多 bar：打 warning 但允许通过（向后兼容）。"""
        targets = _make_targets(1)
        import logging
        caplog.set_level(logging.WARNING)
        result = validate_per_bar_targets(targets, 5, "test_strat", "TEST")
        assert result is targets
        assert "LEGACY" in caplog.text

    def test_empty_targets_raises(self):
        """空列表抛错。"""
        with pytest.raises(ValueError, match="returned empty list"):
            validate_per_bar_targets([], 0, "test_strat", "TEST")

    def test_missing_bar_date_raises(self):
        """target 缺 bar_date：抛 ValueError。"""
        targets = [
            PositionTarget(symbol="TEST", target_weight=0.1, metadata={"reason": "test"}),
        ]
        with pytest.raises(ValueError, match="missing metadata.bar_date"):
            validate_per_bar_targets(targets, 1, "test_strat", "TEST")

    def test_all_have_bar_date_passes(self):
        """所有 target 都有 bar_date：通过。"""
        targets = _make_targets(10)
        result = validate_per_bar_targets(targets, 10, "test_strat", "TEST")
        assert result is targets


class TestPositionTargetBarDate:
    """PositionTarget.bar_date 属性测试。"""

    def test_bar_date_returns_metadata_value(self):
        pt = PositionTarget(
            symbol="TEST",
            target_weight=0.2,
            metadata={"bar_date": "2024-06-15", "reason": "test"},
        )
        assert pt.bar_date == "2024-06-15"

    def test_bar_date_returns_none_when_missing(self):
        pt = PositionTarget(symbol="TEST", target_weight=0.2, metadata={"reason": "no_date"})
        assert pt.bar_date is None

    def test_bar_date_none_with_empty_metadata(self):
        pt = PositionTarget(symbol="TEST", target_weight=0.2)
        assert pt.bar_date is None
