"""Integration tests for real run_with_positions() matching engine.

Covers: buy, sell, cash change, equity change, insufficient funds,
limit up/down skip, 100-share lot, fees, suspension skip.
"""

import pytest
import pandas as pd
import numpy as np

from backend.core.engine import BacktestEngine
from backend.core.strategy import PositionTarget
from backend.core.strategies.target_weight_demo import TargetWeightDemoStrategy


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_df(periods=20, seed=42, start_price=10.0, volatility=0.02):
    """Build mock OHLCV DataFrame with ascending dates."""
    dates = pd.date_range("2024-01-02", periods=periods, freq="B")
    np.random.seed(seed)
    prices = [start_price]
    for _ in range(1, len(dates)):
        prices.append(prices[-1] * (1 + np.random.normal(0, volatility)))
    prices = np.array(prices)

    return pd.DataFrame({
        "date": dates,
        "open": prices * 0.99,
        "close": prices,
        "high": prices * 1.02,
        "low": prices * 0.98,
        "volume": np.random.randint(1_000_000, 10_000_000, len(dates)),
        "trade_signal": 0,
        "limit_ratio": 0.10,
    })


def _targets_for_df(df, weight_schedule, symbol="TEST"):
    """Build PositionTarget list matching df rows with given weight schedule.

    weight_schedule: dict mapping bar_index -> target_weight.
    Bars not in the dict get weight=0.0.
    """
    targets = []
    for i in range(len(df)):
        trade_date = df["date"].iloc[i].strftime("%Y-%m-%d")
        tw = weight_schedule.get(i, 0.0)
        targets.append(PositionTarget(
            symbol=symbol,
            target_weight=tw,
            confidence=0.8,
            metadata={"bar_date": trade_date},
        ))
    return targets


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

class TestTargetWeightDemoStrategyTimeline:
    """Regression coverage for dynamic per-bar target weights."""

    def test_strategy_generates_bar_dated_targets_not_one_static_final_target(self):
        df = _make_df(periods=40, start_price=10.0, volatility=0.04)
        strategy = TargetWeightDemoStrategy({
            "rsi_period": 7,
            "max_target_weight": 0.30,
            "oversold_floor": 30,
            "overbought_ceiling": 70,
        })

        targets = strategy.generate_targets(df, "TEST")

        assert len(targets) == len(df)
        assert all(t.metadata.get("bar_date") for t in targets)
        assert len({t.target_weight for t in targets}) > 1

    def test_engine_uses_bar_dated_targets_instead_of_reusing_final_weight(self):
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        df = _make_df(periods=40, start_price=10.0, volatility=0.04)
        strategy = TargetWeightDemoStrategy({
            "rsi_period": 7,
            "max_target_weight": 0.30,
            "oversold_floor": 30,
            "overbought_ceiling": 70,
        })
        targets = strategy.generate_targets(df, "TEST")
        result = engine.run_with_positions(df, "TEST", targets)

        target_weights = result["data"]["target_weight"].tolist()
        assert len({round(float(w), 6) for w in target_weights}) > 1
        assert target_weights == [t.target_weight for t in targets]


class TestRealMatchingEngineBuy:
    """Buy-side behaviour."""

    def test_buy_success_increases_shares_and_reduces_cash(self):
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        df = _make_df(periods=5)
        # target_weight=0.10 on all bars → engine should buy on bar 0
        targets = _targets_for_df(df, {0: 0.10, 1: 0.10, 2: 0.10, 3: 0.10, 4: 0.10})
        result = engine.run_with_positions(df, "TEST", targets)

        logs = result["logs"]
        buy_logs = [l for l in logs if l["action"] == "buy"]
        assert len(buy_logs) >= 1, "Should have at least one buy"
        first_buy = buy_logs[0]
        assert first_buy["shares"] > 0, "Should have bought some shares"
        assert first_buy["shares"] % 100 == 0, "Shares should be in lots of 100"
        assert first_buy["fee"] >= 0

        metadata = result["metadata"]
        assert metadata["position_mode"] == "target_weight"
        assert metadata["final_shares"] > 0

    def test_buy_insufficient_cash_skips_or_trims(self):
        """With very small cash and high price, buy should be trimmed or skipped."""
        engine = BacktestEngine(initial_cash=500, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        df = _make_df(periods=3, start_price=100.0)
        targets = _targets_for_df(df, {0: 0.30})  # wants 30% of equity = 150 worth, but only 500 cash
        result = engine.run_with_positions(df, "TEST", targets)

        logs = result["logs"]
        buy_logs = [l for l in logs if l["action"] == "buy"]
        # With 500 cash and ~100 price: 500/100 = 5 shares → 0 lots of 100
        # So either buy_failed or hold
        if buy_logs:
            assert buy_logs[0]["shares"] == 0 or "trimmed" in buy_logs[0]["reason"] or "failed" in buy_logs[0]["reason"]
        metadata = result["metadata"]
        # Final shares should be 0 or very small
        assert metadata["final_shares"] >= 0

    def test_buy_respects_lot_size(self):
        """Shares must always be in multiples of 100."""
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        df = _make_df(periods=5)
        targets = _targets_for_df(df, {0: 0.15, 1: 0.15, 2: 0.15, 3: 0.15, 4: 0.15})
        result = engine.run_with_positions(df, "TEST", targets)

        logs = result["logs"]
        for l in logs:
            if l["action"] == "buy" and l["shares"] > 0:
                assert l["shares"] % 100 == 0, f"Shares {l['shares']} not a multiple of 100"


class TestRealMatchingEngineSell:
    """Sell-side behaviour."""

    def test_sell_reduces_shares_and_increases_cash(self):
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        df = _make_df(periods=10)
        # Buy first (weight=0.20), then reduce to 0.05
        schedule = {i: 0.20 for i in range(5)}
        schedule.update({i: 0.05 for i in range(5, 10)})
        targets = _targets_for_df(df, schedule)
        result = engine.run_with_positions(df, "TEST", targets)

        logs = result["logs"]
        sell_logs = [l for l in logs if l["action"] == "sell"]
        assert len(sell_logs) >= 1, f"Should have at least one sell, got {len(sell_logs)}"
        for sl in sell_logs:
            assert sl["shares"] > 0
            assert sl["shares"] % 100 == 0

    def test_sell_does_not_exceed_holdings(self):
        """Cannot sell more than current position."""
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        df = _make_df(periods=8)
        # Weight goes from 0.30 → 0.0 (full exit)
        schedule = {i: 0.30 for i in range(4)}
        schedule.update({i: 0.0 for i in range(4, 8)})
        targets = _targets_for_df(df, schedule)
        result = engine.run_with_positions(df, "TEST", targets)

        logs = result["logs"]
        sell_logs = [l for l in logs if l["action"] == "sell"]
        assert len(sell_logs) >= 1, "Should sell to exit position"
        # After the sell, shares should be 0
        metadata = result["metadata"]
        assert metadata["final_shares"] == 0, f"Should have exited fully, got {metadata['final_shares']} shares"


class TestRealMatchingEngineAccount:
    """Account state correctness."""

    def test_cash_decreases_on_buy_increases_on_sell(self):
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        df = _make_df(periods=10)
        schedule = {i: 0.20 for i in range(5)}
        schedule.update({i: 0.0 for i in range(5, 10)})
        targets = _targets_for_df(df, schedule)
        result = engine.run_with_positions(df, "TEST", targets)

        logs = result["logs"]
        buy_log = next((l for l in logs if l["action"] == "buy"), None)
        sell_log = next((l for l in logs if l["action"] == "sell"), None)

        assert buy_log is not None, "Should have a buy"
        assert sell_log is not None, "Should have a sell"
        assert buy_log["cash_after"] < 100_000, "Cash should decrease after buy"
        assert sell_log["cash_after"] > buy_log["cash_after"], "Cash should increase after sell"

    def test_total_equity_changes_with_price(self):
        """Equity curve should vary with price movements, not stay flat."""
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        df = _make_df(periods=20)
        targets = _targets_for_df(df, {i: 0.15 for i in range(20)})
        result = engine.run_with_positions(df, "TEST", targets)

        equity = result["data"]["total_equity"].tolist()
        assert len(set(round(e, 2) for e in equity)) > 1, "Equity should not be constant"

    def test_fees_are_deducted(self):
        """With non-zero commission and tax, fees should appear in logs."""
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0003, tax_rate=0.001, slippage_rate=0.0001)
        df = _make_df(periods=20)
        schedule = {i: 0.20 for i in range(10)}
        schedule.update({i: 0.05 for i in range(10, 20)})
        targets = _targets_for_df(df, schedule)
        result = engine.run_with_positions(df, "TEST", targets)

        logs = result["logs"]
        fee_logs = [l for l in logs if l.get("fee", 0) > 0]
        assert len(fee_logs) > 0, "Should have non-zero fee logs"
        for fl in fee_logs:
            assert fl["commission"] >= 0
            # tax only on sell
            if fl["action"] == "sell":
                assert fl["tax"] >= 0


class TestRealMatchingEngineMetricsContract:
    """Metrics returned to detail/summary pages should have stable fields."""

    def test_closed_trade_metrics_have_numeric_and_display_fields(self):
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        df = _make_df(periods=10)
        schedule = {i: 0.20 for i in range(5)}
        schedule.update({i: 0.0 for i in range(5, 10)})
        targets = _targets_for_df(df, schedule)
        result = engine.run_with_positions(df, "TEST", targets)

        metadata = result["metadata"]
        assert metadata["closed_trade_count"] >= 1
        assert metadata["has_closed_trades"] is True
        assert isinstance(metadata["win_rate"], float | int)
        assert isinstance(metadata["pnl_ratio"], float | int)
        assert metadata["win_rate_display"].endswith("%")
        assert metadata["pnl_ratio_display"] != "--"

    def test_no_closed_trade_metrics_keep_fields_but_display_as_empty(self):
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        df = _make_df(periods=5)
        targets = _targets_for_df(df, {i: 0.20 for i in range(5)})
        result = engine.run_with_positions(df, "TEST", targets)

        metadata = result["metadata"]
        assert metadata["closed_trade_count"] == 0
        assert metadata["has_closed_trades"] is False
        assert metadata["win_rate"] == 0.0
        assert metadata["pnl_ratio"] == 0.0
        assert metadata["win_rate_display"] == "--"
        assert metadata["pnl_ratio_display"] == "--"


class TestRealMatchingEngineConstraints:
    """Market constraints: suspension, limit up/down."""

    def test_suspended_stock_skips_trading(self):
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        df = _make_df(periods=5)
        df["volume"] = 0  # All bars suspended
        targets = _targets_for_df(df, {0: 0.20, 1: 0.20, 2: 0.20, 3: 0.20, 4: 0.20})
        result = engine.run_with_positions(df, "TEST", targets)

        logs = result["logs"]
        buy_logs = [l for l in logs if l["action"] == "buy"]
        assert len(buy_logs) == 0, "Should not buy on suspended stock"
        failed_logs = [l for l in logs if "failed" in l["action"]]
        assert len(failed_logs) >= 1, "Should have failed logs"
        for fl in failed_logs:
            assert "停牌" in fl["reason"], f"Reason should mention suspension: {fl['reason']}"

    def test_limit_up_skips_buy(self):
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        dates = pd.date_range("2024-01-02", periods=5, freq="B")
        # Bar 0: normal price (10.0) → 可以买入
        # Bars 1-4: open=11.0, close=10.9 → 相对 prev_close=10.0 涨幅 >=10% → 涨停
        df = pd.DataFrame({
            "date": dates,
            "open": [10.0, 11.0, 11.0, 11.0, 11.0],
            "close": [9.9, 10.9, 10.9, 10.9, 10.9],
            "high": [10.0, 11.0, 11.0, 11.0, 11.0],
            "low": [9.9, 10.9, 10.9, 10.9, 10.9],
            "volume": [1_000_000] * 5,
            "trade_signal": 0,
            "limit_ratio": 0.10,
        })
        # Rising target_weight → engine always wants to BUY MORE
        targets = _targets_for_df(df, {0: 0.10, 1: 0.15, 2: 0.20, 3: 0.25, 4: 0.30})
        result = engine.run_with_positions(df, "TEST", targets)

        logs = result["logs"]
        buy_failed = [l for l in logs if "buy_failed" in l["action"]]
        assert len(buy_failed) >= 1, f"Should have buy failures on limit-up bars, got {len(buy_failed)}"
        for bf in buy_failed:
            assert "涨停" in bf["reason"] or "limit" in bf["reason"].lower()

    def test_limit_down_skips_sell(self):
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        df = _make_df(periods=10, start_price=10.0, volatility=0.0)
        df["close"] = 10.0
        df["volume"] = 1_000_000

        # First 5 bars: normal price → buy. Then limit down → cannot sell.
        df.loc[0:4, "open"] = 9.9   # Normal
        df.loc[5:9, "open"] = 9.0   # 10% down from 10.0 → limit down

        schedule = {i: 0.20 for i in range(5)}
        schedule.update({i: 0.0 for i in range(5, 10)})  # Want to sell during limit down
        targets = _targets_for_df(df, schedule)
        result = engine.run_with_positions(df, "TEST", targets)

        logs = result["logs"]
        sell_logs = [l for l in logs if l["action"] == "sell"]
        # On limit down bars, sell should fail, so no successful sell
        sell_failed = [l for l in logs if "sell_failed" in l["action"] or ("failed" in l["action"] and "sell" in l["action"])]
        assert len(sell_failed) >= 1, "Should have sell failures on limit down"

    def test_slippage_applied_on_buy_and_sell(self):
        """With non-zero slippage, fill prices should be adjusted."""
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.01)
        df = _make_df(periods=10, start_price=10.0, volatility=0.0)
        df["open"] = 10.0
        df["close"] = 10.0
        df["volume"] = 1_000_000

        schedule = {i: 0.20 for i in range(5)}
        schedule.update({i: 0.0 for i in range(5, 10)})
        targets = _targets_for_df(df, schedule)
        result = engine.run_with_positions(df, "TEST", targets)

        logs = result["logs"]
        buy_log = next((l for l in logs if l["action"] == "buy"), None)
        sell_log = next((l for l in logs if l["action"] == "sell"), None)

        assert buy_log is not None, "Should have a buy"
        # Buy fill = open * (1 + slippage) = 10.0 * 1.01 = 10.10
        assert buy_log["price"] > 10.0, f"Buy price should include slippage, got {buy_log['price']}"

        if sell_log:
            # Sell fill = open * (1 - slippage) = 10.0 * 0.99 = 9.90
            assert sell_log["price"] < 10.0, f"Sell price should include slippage, got {sell_log['price']}"
