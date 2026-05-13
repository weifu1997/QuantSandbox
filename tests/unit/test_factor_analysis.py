import numpy as np
import pandas as pd

from backend.research.factor_analysis import analyze_factor_ic
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


def _make_cross_section_dataset(kind: str, days: int = 3, per_day: int = 12) -> pd.DataFrame:
    rows = []
    base_date = pd.Timestamp("2024-01-02")
    rng = np.random.default_rng(42)
    for d in range(days):
        date = base_date + pd.Timedelta(days=d)
        for i in range(per_day):
            factor = float(i + 1)
            if kind == "positive":
                future = factor * 0.01
            elif kind == "negative":
                future = -factor * 0.01
            elif kind == "random":
                future = float(rng.normal())
            else:
                raise ValueError(kind)
            rows.append(
                {
                    "date": date,
                    "ticker": f"T{i:03d}",
                    "factor:test_factor": factor,
                    "future_return_5d": future,
                    "is_valid_sample": True,
                    "missing_reason": "",
                }
            )
    return pd.DataFrame(rows)


def test_analyze_factor_ic_perfect_positive_correlation_near_one():
    dataset = _make_cross_section_dataset("positive")

    report = analyze_factor_ic(
        dataset=dataset,
        factor_name="test_factor",
        horizons=[5],
        min_cross_section=10,
        factor_library=StubLibrary(higher_is_better=True),
    )

    stats = report.horizons[5]
    assert stats.ic_mean > 0.999
    assert stats.rank_ic_mean > 0.999
    assert stats.positive_ic_ratio == 1.0
    assert stats.sample_count == 3



def test_analyze_factor_ic_perfect_negative_correlation_near_minus_one():
    dataset = _make_cross_section_dataset("negative")

    report = analyze_factor_ic(
        dataset=dataset,
        factor_name="test_factor",
        horizons=[5],
        min_cross_section=10,
        factor_library=StubLibrary(higher_is_better=True),
    )

    stats = report.horizons[5]
    assert stats.ic_mean < -0.999
    assert stats.rank_ic_mean < -0.999
    assert stats.positive_ic_ratio == 0.0



def test_analyze_factor_ic_random_data_near_zero():
    dataset = _make_cross_section_dataset("random", days=20, per_day=20)

    report = analyze_factor_ic(
        dataset=dataset,
        factor_name="test_factor",
        horizons=[5],
        min_cross_section=10,
        factor_library=StubLibrary(higher_is_better=True),
    )

    stats = report.horizons[5]
    assert abs(stats.ic_mean) < 0.35
    assert abs(stats.rank_ic_mean) < 0.35



def test_analyze_factor_ic_handles_missing_values_without_crash():
    dataset = _make_cross_section_dataset("positive", days=3, per_day=12)
    dataset.loc[0:4, "factor:test_factor"] = np.nan
    dataset.loc[5:8, "future_return_5d"] = np.nan

    report = analyze_factor_ic(
        dataset=dataset,
        factor_name="test_factor",
        horizons=[5],
        min_cross_section=5,
        factor_library=StubLibrary(higher_is_better=True),
    )

    stats = report.horizons[5]
    assert stats.sample_count >= 1
    assert 0.0 < stats.missing_ratio < 1.0



def test_analyze_factor_ic_flips_direction_when_higher_is_better_false():
    dataset = _make_cross_section_dataset("negative")

    report = analyze_factor_ic(
        dataset=dataset,
        factor_name="test_factor",
        horizons=[5],
        min_cross_section=10,
        factor_library=StubLibrary(higher_is_better=False),
    )

    stats = report.horizons[5]
    assert stats.ic_mean > 0.999
    assert stats.rank_ic_mean > 0.999



def test_analyze_factor_ic_emits_warning_when_cross_section_too_small():
    dataset = _make_cross_section_dataset("positive", days=2, per_day=5)

    report = analyze_factor_ic(
        dataset=dataset,
        factor_name="test_factor",
        horizons=[5],
        min_cross_section=10,
        factor_library=StubLibrary(higher_is_better=True),
    )

    stats = report.horizons[5]
    assert stats.sample_count == 0
    assert report.warnings
    assert any("min_cross_section" in warning for warning in report.warnings)
