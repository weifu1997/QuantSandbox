import math

import pandas as pd

from backend.research.factor_library import ResearchFactorLibrary, get_research_factor_library


def _make_df(rows: int = 160, with_fundamentals: bool = True) -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=rows, freq="B")
    close = pd.Series([100 + i for i in range(rows)], dtype="float64")
    volume = pd.Series([1_000_000 + i * 1000 for i in range(rows)], dtype="float64")
    amount = close * volume
    data = {
        "date": dates,
        "open": close - 1,
        "high": close + 2,
        "low": close - 2,
        "close": close,
        "volume": volume,
        "amount": amount,
    }
    if with_fundamentals:
        data["pe_ttm"] = pd.Series([10 + (i % 20) for i in range(rows)], dtype="float64")
        data["pb"] = pd.Series([1 + (i % 10) * 0.1 for i in range(rows)], dtype="float64")
        data["dividend_yield"] = pd.Series([2 + (i % 5) * 0.1 for i in range(rows)], dtype="float64")
    return pd.DataFrame(data)


def test_library_lists_expected_v1_factors():
    library = get_research_factor_library()
    names = set(library.list_names())

    assert "momentum_20d" in names
    assert "reversal_5d" in names
    assert "ma5_ma20" in names
    assert "volatility_20d" in names
    assert "volume_ratio_20d" in names
    assert "pe_ttm" in names


def test_each_factor_output_length_matches_input_df():
    df = _make_df()
    library = get_research_factor_library()

    for name in ["momentum_20d", "reversal_5d", "ma5_ma20", "volatility_20d", "volume_ratio_20d", "pe_ttm"]:
        series = library.compute_factor(name, df)
        assert len(series) == len(df), name



def test_momentum_20d_matches_formula():
    df = _make_df()
    library = get_research_factor_library()

    series = library.compute_factor("momentum_20d", df)

    expected = (df.loc[25, "close"] / df.loc[5, "close"]) - 1
    assert round(series.iloc[25], 10) == round(expected, 10)



def test_reversal_5d_matches_negative_short_term_return():
    df = _make_df()
    library = get_research_factor_library()

    series = library.compute_factor("reversal_5d", df)

    expected = -((df.loc[10, "close"] / df.loc[5, "close"]) - 1)
    assert round(series.iloc[10], 10) == round(expected, 10)



def test_warmup_periods_are_nan_when_expected():
    df = _make_df()
    library = get_research_factor_library()

    assert library.compute_factor("momentum_20d", df).iloc[:20].isna().all()
    assert library.compute_factor("ma20_ma60", df).iloc[:59].isna().all()
    assert library.compute_factor("volatility_20d", df).iloc[:19].isna().all()



def test_valuation_factors_missing_columns_return_nan_not_error():
    df = _make_df(with_fundamentals=False)
    library = get_research_factor_library()

    pe = library.compute_factor("pe_ttm", df)
    pb = library.compute_factor("pb", df)
    dy = library.compute_factor("dividend_yield", df)

    assert pe.isna().all()
    assert pb.isna().all()
    assert dy.isna().all()



def test_factor_output_contains_no_infinite_values():
    df = _make_df()
    library = get_research_factor_library()

    for name in [
        "momentum_20d",
        "momentum_20d_skip5d",
        "reversal_5d",
        "ma5_ma20",
        "ma20_ma60",
        "volatility_20d",
        "atr_pct_14",
        "volume_ratio_20d",
    ]:
        series = library.compute_factor(name, df)
        non_na = series.dropna()
        assert all(math.isfinite(float(v)) for v in non_na), name
