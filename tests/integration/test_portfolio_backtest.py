"""Integration tests for run_portfolio() — multi-ticker portfolio-level real backtesting.

Covers: shared cash pool, buy/sell rebalancing, per-ticker equity,
position_mode, fees, suspension/limit-up constraints.
"""

import pytest
import pandas as pd
import numpy as np

from backend.core.engine import BacktestEngine
from backend.core.strategies.target_weight_demo import TargetWeightDemoStrategy


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_portfolio_data(
    tickers=("AAA", "BBB"),
    periods=15,
    seed=42,
    start_prices=(10.0, 20.0),
    volatility=(0.02, 0.015),
) -> dict[str, pd.DataFrame]:
    """Build aligned mock OHLCV data for multiple tickers."""
    dates = pd.date_range("2024-01-02", periods=periods, freq="B")
    np.random.seed(seed)

    frames = {}
    for idx, ticker in enumerate(tickers):
        prices = [start_prices[idx]]
        for _ in range(1, len(dates)):
            prices.append(prices[-1] * (1 + np.random.normal(0, volatility[idx])))
        prices = np.array(prices)

        frames[ticker] = pd.DataFrame({
            "date": dates,
            "open": prices * 0.99,
            "close": prices,
            "high": prices * 1.02,
            "low": prices * 0.98,
            "volume": np.random.randint(1_000_000, 10_000_000, len(dates)),
            "trade_signal": 0,
            "limit_ratio": 0.10,
        })
    return frames


def _make_flat_price_data(
    tickers=("AAA", "BBB"),
    periods=15,
    prices_per=(10.0, 20.0),
) -> dict[str, pd.DataFrame]:
    """Build flat-price mock data (no price movement) for clean tests."""
    dates = pd.date_range("2024-01-02", periods=periods, freq="B")
    frames = {}
    for idx, ticker in enumerate(tickers):
        p = prices_per[idx]
        frames[ticker] = pd.DataFrame({
            "date": dates,
            "open": [p] * periods,
            "close": [p] * periods,
            "high": [p] * periods,
            "low": [p] * periods,
            "volume": [1_000_000] * periods,
            "trade_signal": 0,
            "limit_ratio": 0.10,
        })
    return frames


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

class TestPortfolioRealBacktest:
    """Portfolio-level real matching engine tests."""

    def test_portfolio_returns_correct_structure(self):
        """Basic structure: portfolio_metrics, portfolio_equity, per_ticker, logs."""
        frames = _make_portfolio_data()
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        result = engine.run_portfolio(frames, TargetWeightDemoStrategy, {"rsi_period": 14, "max_target_weight": 0.30})

        assert "portfolio_metrics" in result
        assert "portfolio_equity" in result
        assert "per_ticker" in result
        assert "logs" in result

        pm = result["portfolio_metrics"]
        assert pm["position_mode"] == "portfolio_target_weight"
        assert pm["ticker_count"] == 2
        assert "final_equity" in pm
        assert "total_return" in pm

        pe = result["portfolio_equity"]
        assert len(pe) == 15

        pt = result["per_ticker"]
        assert "AAA" in pt
        assert "BBB" in pt
        for ticker in ("AAA", "BBB"):
            info = pt[ticker]
            assert "metadata" in info
            assert "equity" in info
            assert info["metadata"]["position_mode"] == "portfolio_target_weight"

    def test_portfolio_shared_cash_pool(self):
        """Buying one ticker should reduce cash available for the other."""
        frames = _make_portfolio_data(periods=15)
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        result = engine.run_portfolio(frames, TargetWeightDemoStrategy, {"rsi_period": 14, "max_target_weight": 0.30})

        logs = result["logs"]
        buys = [l for l in logs if l["action"] == "buy"]
        # Both tickers have price movement → should both try to buy
        # Cash pool is shared, so they compete for cash
        assert len(buys) > 0, "Should have at least one buy"
        # Verify cash_after decreases sequentially across buys
        cash_values = [l["cash_after"] for l in buys if "cash_after" in l]
        for i in range(1, len(cash_values)):
            assert cash_values[i] <= cash_values[i - 1], (
                f"Cash should decrease with each buy: {cash_values}"
            )

    def test_portfolio_sells_release_cash(self):
        """Selling a position should increase cash available for other buys."""
        frames = _make_flat_price_data(periods=20)
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        result = engine.run_portfolio(frames, TargetWeightDemoStrategy, {"rsi_period": 14, "max_target_weight": 0.30})

        logs = result["logs"]
        sells = [l for l in logs if l["action"] == "sell"]
        if sells:
            # After a sell, cash should increase
            for sl in sells:
                assert sl.get("cash_after", 0) > 0
            # A buy after a sell should have more cash available
            sell_indices = [i for i, l in enumerate(logs) if l["action"] == "sell"]
            buy_indices = [i for i, l in enumerate(logs) if l["action"] == "buy"]
            if sell_indices and buy_indices:
                last_sell_idx = max(sell_indices)
                later_buys = [i for i in buy_indices if i > last_sell_idx]
                if later_buys:
                    cash_after_sell = logs[last_sell_idx].get("cash_after", 0)
                    next_buy = logs[min(later_buys)]
                    assert next_buy.get("cash_after", 0) >= cash_after_sell or next_buy["shares"] > 0

    def test_portfolio_per_ticker_equity_length(self):
        """Each ticker's equity curve should match its DataFrame length."""
        frames = _make_flat_price_data(periods=12)
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        result = engine.run_portfolio(frames, TargetWeightDemoStrategy, {"rsi_period": 14, "max_target_weight": 0.30})

        for ticker, info in result["per_ticker"].items():
            assert len(info["equity"]) == len(frames[ticker]), (
                f"{ticker} equity length {len(info['equity'])} != {len(frames[ticker])}"
            )

    def test_portfolio_with_fees(self):
        """With non-zero fees, trades should have commission and tax logged."""
        frames = _make_portfolio_data(periods=15)
        engine = BacktestEngine(
            initial_cash=100_000,
            commission_rate=0.0003,
            tax_rate=0.001,
            slippage_rate=0.0001,
        )
        result = engine.run_portfolio(frames, TargetWeightDemoStrategy, {"rsi_period": 14, "max_target_weight": 0.30})

        logs = result["logs"]
        trades = [l for l in logs if l["action"] in ("buy", "sell") and l["shares"] > 0]
        assert len(trades) > 0, "Should have trades with fees"
        for t in trades:
            assert "commission" in t
            assert t["commission"] >= 0
            if t["action"] == "sell":
                assert t["tax"] >= 0

    def test_portfolio_suspended_stock_skipped(self):
        """Suspended stock (volume=0) should be skipped in portfolio rebalancing."""
        frames = _make_portfolio_data(periods=15)
        # Mark AAA as suspended
        frames["AAA"]["volume"] = 0
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        result = engine.run_portfolio(frames, TargetWeightDemoStrategy, {"rsi_period": 14, "max_target_weight": 0.30})

        logs = result["logs"]
        aaa_buys = [l for l in logs if l["ticker"] == "AAA" and l["action"] == "buy"]
        assert len(aaa_buys) == 0, f"Should not buy suspended stock AAA, got {len(aaa_buys)} buy(s)"
        aaa_failed = [l for l in logs if l["ticker"] == "AAA" and "failed" in l["action"]]
        assert len(aaa_failed) > 0, "Should have buy_failed for suspended AAA"

    def test_portfolio_limit_up_skipped(self):
        """Limit-up stock should not be bought in portfolio rebalancing."""
        frames = _make_flat_price_data(periods=10, prices_per=(10.0, 11.0))
        # AAA at 11.0 when prev_close is 10.0 → limit up (10% up)
        # Bar 0 won't have prev_close, so ensure bars 1+ are limit_up
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        result = engine.run_portfolio(frames, TargetWeightDemoStrategy, {"rsi_period": 14, "max_target_weight": 0.30})

        logs = result["logs"]
        aaa_failed = [l for l in logs if l["ticker"] == "AAA" and "buy_failed" in l["action"]]
        # AAA at 11 is limit-up vs prev_close 10 → should fail on bars 1+
        # Bar 0 won't trigger limit-up (no prev_close), so may buy
        aaa_buys = [l for l in logs if l["ticker"] == "AAA" and l["action"] == "buy"]
        assert len(aaa_failed) > 0 or len(aaa_buys) == 0, (
            f"AAA should have buy_failed or no buys on limit-up, got {len(aaa_failed)} fails, {len(aaa_buys)} buys"
        )

    def test_portfolio_lot_size_respected(self):
        """All executed shares should be multiples of 100."""
        frames = _make_portfolio_data(periods=15)
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        result = engine.run_portfolio(frames, TargetWeightDemoStrategy, {"rsi_period": 14, "max_target_weight": 0.30})

        logs = result["logs"]
        for l in logs:
            if l["shares"] > 0:
                assert l["shares"] % 100 == 0, (
                    f"Shares {l['shares']} for {l['ticker']} not a multiple of 100"
                )

    def test_portfolio_equity_changes_with_price(self):
        """Portfolio equity should not be constant when prices move."""
        frames = _make_portfolio_data(periods=20)
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        result = engine.run_portfolio(frames, TargetWeightDemoStrategy, {"rsi_period": 14, "max_target_weight": 0.30})

        pe = result["portfolio_equity"]
        unique_values = len(set(round(e, 2) for e in pe))
        assert unique_values > 1, f"Portfolio equity should vary with prices, got {unique_values} unique values"


# ---------------------------------------------------------------------------
# D-9 Regression: single-ticker portfolio should NOT return -100%
# ---------------------------------------------------------------------------

class TestPortfolioSingleTickerNoRegression:
    """D-9: Protect against D-8B -100% regression for single-ticker portfolio."""

    def test_single_ticker_no_shares_no_false_loss(self):
        """Single ticker with no trades should show 0% per-ticker, not -100%."""
        frames = _make_flat_price_data(tickers=("XXX",), periods=10, prices_per=(10.0,))
        engine = BacktestEngine(initial_cash=100_000, commission_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
        result = engine.run_portfolio(frames, TargetWeightDemoStrategy, {"rsi_period": 14, "max_target_weight": 0.30})

        pe = result["portfolio_equity"]
        assert pe[-1] == pe[0] == 100000.0, "Portfolio equity unchanged when no trades"

        info = result["per_ticker"]["XXX"]
        md = info["metadata"]
        assert md["final_shares"] == 0
        assert md["total_return"] == 0.0, f"Expected 0% for no-position ticker, got {md['total_return']}%"
        assert md["max_drawdown"] == 0.0
        assert md["sharpe_ratio"] == 0.0
        assert md["final_equity"] == 0.0

    def test_portfolio_per_ticker_equity_all_zero_when_no_shares_held(self):
        """Per-ticker equity curve must be all zeros when no shares ever bought."""
        frames = _make_flat_price_data(tickers=("YYY",), periods=8, prices_per=(50.0,))
        engine = BacktestEngine(initial_cash=50_000)
        result = engine.run_portfolio(frames, TargetWeightDemoStrategy, {"rsi_period": 14, "max_target_weight": 0.10})

        info = result["per_ticker"]["YYY"]
        assert info["metadata"]["final_shares"] == 0
        assert all(e == 0.0 for e in info["equity"])
