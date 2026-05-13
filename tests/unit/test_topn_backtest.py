import pandas as pd

from backend.research.topn_backtest import run_topn_backtest


def _make_topn_dataset(kind: str, days: int = 8, per_day: int = 20) -> pd.DataFrame:
    rows = []
    base_date = pd.Timestamp("2024-01-02")
    for d in range(days):
        date = base_date + pd.Timedelta(days=d)
        for i in range(per_day):
            factor = float(i + 1)
            if kind == "positive":
                future = factor * 0.001
            elif kind == "negative":
                future = (per_day - i) * 0.001
            else:
                raise ValueError(kind)
            rows.append(
                {
                    "date": date,
                    "ticker": f"T{i:03d}",
                    "factor:test_factor": factor,
                    "future_return_20d": future,
                    "is_valid_sample": True,
                }
            )
    return pd.DataFrame(rows)


def test_topn_backtest_runs_and_outputs_equity_curve():
    dataset = _make_topn_dataset("positive")

    report = run_topn_backtest(
        dataset=dataset,
        factor_name="test_factor",
        horizon=20,
        top_n=5,
        rebalance_frequency="W",
        weighting="equal",
        transaction_cost_bps=10,
        benchmark="equal_weight_universe",
    )

    assert report.total_return > 0
    assert len(report.equity_curve) > 0
    assert report.holdings_by_rebalance_date



def test_topn_backtest_cost_higher_reduces_return():
    dataset = _make_topn_dataset("positive")

    low_cost = run_topn_backtest(
        dataset=dataset,
        factor_name="test_factor",
        horizon=20,
        top_n=5,
        rebalance_frequency="W",
        weighting="equal",
        transaction_cost_bps=0,
        benchmark="equal_weight_universe",
    )
    high_cost = run_topn_backtest(
        dataset=dataset,
        factor_name="test_factor",
        horizon=20,
        top_n=5,
        rebalance_frequency="W",
        weighting="equal",
        transaction_cost_bps=200,
        benchmark="equal_weight_universe",
    )

    assert high_cost.cost_paid > low_cost.cost_paid
    assert high_cost.total_return < low_cost.total_return



def test_topn_backtest_outperforms_equal_weight_when_factor_predictive():
    dataset = _make_topn_dataset("positive")

    report = run_topn_backtest(
        dataset=dataset,
        factor_name="test_factor",
        horizon=20,
        top_n=5,
        rebalance_frequency="W",
        weighting="equal",
        transaction_cost_bps=0,
        benchmark="equal_weight_universe",
    )

    assert report.excess_return_vs_equal_weight > 0
    assert report.excess_return_vs_benchmark > 0



def test_topn_backtest_reverse_signal_can_underperform():
    dataset = _make_topn_dataset("negative")

    report = run_topn_backtest(
        dataset=dataset,
        factor_name="test_factor",
        horizon=20,
        top_n=5,
        rebalance_frequency="W",
        weighting="equal",
        transaction_cost_bps=0,
        benchmark="equal_weight_universe",
    )

    assert report.excess_return_vs_equal_weight < 0



def test_topn_backtest_supports_score_weighting():
    dataset = _make_topn_dataset("positive")

    report = run_topn_backtest(
        dataset=dataset,
        factor_name="test_factor",
        horizon=20,
        top_n=5,
        rebalance_frequency="W",
        weighting="score",
        transaction_cost_bps=0,
        benchmark="equal_weight_universe",
    )

    assert report.total_return > 0
    assert report.turnover >= 0
    first_holding = next(iter(report.holdings_by_rebalance_date.values()))
    assert len(first_holding) == 5



def test_topn_backtest_supports_buy_hold_universe_average_benchmark():
    dataset = _make_topn_dataset("positive")

    report = run_topn_backtest(
        dataset=dataset,
        factor_name="test_factor",
        horizon=20,
        top_n=5,
        rebalance_frequency="W",
        weighting="equal",
        transaction_cost_bps=0,
        benchmark="buy_hold_universe_average",
    )

    assert report.benchmark_name == "buy_hold_universe_average"
    assert len(report.benchmark_equity_curve) == len(report.equity_curve)



def test_topn_backtest_outputs_core_metrics():
    dataset = _make_topn_dataset("positive")

    report = run_topn_backtest(
        dataset=dataset,
        factor_name="test_factor",
        horizon=20,
        top_n=5,
        rebalance_frequency="W",
        weighting="equal",
        transaction_cost_bps=10,
        benchmark="equal_weight_universe",
    )

    assert isinstance(report.annual_return, float)
    assert isinstance(report.total_return, float)
    assert isinstance(report.max_drawdown, float)
    assert isinstance(report.sharpe, float)
    assert isinstance(report.volatility, float)
    assert isinstance(report.turnover, float)
    assert isinstance(report.win_rate, float)
    assert isinstance(report.cost_paid, float)
