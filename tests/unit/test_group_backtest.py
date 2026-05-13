import pandas as pd

from backend.research.group_backtest import run_group_backtest
from backend.research.factor_library import ResearchFactor


class StubLibrary:
    def __init__(self, higher_is_better: bool = True):
        self.factor = ResearchFactor(
            name="test_factor",
            category="test",
            description="stub",
            higher_is_better=higher_is_better,
            required_columns=[],
            min_periods=0,
            compute=lambda df: df["factor:test_factor"],
        )

    def get(self, name: str):
        assert name == "test_factor"
        return self.factor


def _make_group_dataset(kind: str, days: int = 6, per_day: int = 25) -> pd.DataFrame:
    rows = []
    base_date = pd.Timestamp("2024-01-02")
    for d in range(days):
        date = base_date + pd.Timedelta(days=d)
        for i in range(per_day):
            factor = float(i + 1)
            if kind == "monotonic":
                future = factor * 0.001
            elif kind == "reverse":
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


def test_group_backtest_monotonic_factor_has_q5_greater_than_q1():
    dataset = _make_group_dataset("monotonic")

    report = run_group_backtest(
        dataset=dataset,
        factor_name="test_factor",
        horizon=20,
        groups=5,
        rebalance_frequency="D",
        factor_library=StubLibrary(higher_is_better=True),
    )

    assert report.group_return_by_group["Q5"] > report.group_return_by_group["Q1"]
    assert report.long_short_return > 0
    assert report.monotonicity_score == 1.0



def test_group_backtest_reverse_factor_has_q1_greater_than_q5():
    dataset = _make_group_dataset("reverse")

    report = run_group_backtest(
        dataset=dataset,
        factor_name="test_factor",
        horizon=20,
        groups=5,
        rebalance_frequency="D",
        factor_library=StubLibrary(higher_is_better=True),
    )

    assert report.group_return_by_group["Q1"] > report.group_return_by_group["Q5"]
    assert report.long_short_return < 0
    assert report.monotonicity_score == 0.0



def test_group_backtest_long_short_return_equals_q5_minus_q1():
    dataset = _make_group_dataset("monotonic")

    report = run_group_backtest(
        dataset=dataset,
        factor_name="test_factor",
        horizon=20,
        groups=5,
        rebalance_frequency="D",
        factor_library=StubLibrary(higher_is_better=True),
    )

    expected = report.group_return_by_group["Q5"] - report.group_return_by_group["Q1"]
    assert round(report.long_short_return, 10) == round(expected, 10)



def test_group_backtest_outputs_equity_curve_and_group_metrics():
    dataset = _make_group_dataset("monotonic")

    report = run_group_backtest(
        dataset=dataset,
        factor_name="test_factor",
        horizon=20,
        groups=5,
        rebalance_frequency="D",
        factor_library=StubLibrary(higher_is_better=True),
    )

    assert len(report.equity_curve_by_group["Q1"]) == 6
    assert len(report.equity_curve_by_group["Q5"]) == 6
    assert "Q3" in report.annual_return_by_group
    assert "Q3" in report.max_drawdown_by_group
    assert "Q3" in report.win_rate_by_group
    assert "Q3" in report.turnover_by_group



def test_group_backtest_small_cross_section_emits_warning():
    dataset = _make_group_dataset("monotonic", days=3, per_day=4)

    report = run_group_backtest(
        dataset=dataset,
        factor_name="test_factor",
        horizon=20,
        groups=5,
        rebalance_frequency="D",
        factor_library=StubLibrary(higher_is_better=True),
    )

    assert report.warnings
    assert any("insufficient" in warning.lower() or "too small" in warning.lower() for warning in report.warnings)



def test_group_backtest_higher_is_better_false_flips_group_order():
    dataset = _make_group_dataset("reverse")

    report = run_group_backtest(
        dataset=dataset,
        factor_name="test_factor",
        horizon=20,
        groups=5,
        rebalance_frequency="D",
        factor_library=StubLibrary(higher_is_better=False),
    )

    assert report.group_return_by_group["Q5"] > report.group_return_by_group["Q1"]
    assert report.long_short_return > 0
