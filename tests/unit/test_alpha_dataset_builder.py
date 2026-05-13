import pandas as pd

from backend.core.factors.registry import FactorRegistry
from backend.core.factors.technical import MaCrossValue
from backend.research.dataset_builder import (
    add_future_returns,
    align_factor_values,
    build_alpha_dataset,
)


class StubDataCenter:
    def __init__(self):
        self.frames = {}

    def add_frame(self, ticker: str, df: pd.DataFrame) -> None:
        self.frames[ticker] = df.copy()

    def fetch_stock_data(self, symbol: str, start_date: str, end_date: str):
        df = self.frames[symbol].copy()
        mask = (df["date"] >= pd.to_datetime(start_date)) & (df["date"] <= pd.to_datetime(end_date))
        return df.loc[mask].reset_index(drop=True)


def _make_df(rows: int = 30, start: str = "2024-01-02", zero_volume_index: int | None = None) -> pd.DataFrame:
    dates = pd.date_range(start, periods=rows, freq="B")
    close = pd.Series(range(10, 10 + rows), dtype="float64")
    volume = pd.Series([1_000_000] * rows, dtype="float64")
    if zero_volume_index is not None:
        volume.iloc[zero_volume_index] = 0
    return pd.DataFrame(
        {
            "date": dates,
            "open": close - 0.2,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": volume,
            "name": ["TEST"] * rows,
        }
    )


def test_add_future_returns_sets_tail_nan_per_horizon():
    df = _make_df(rows=10)

    result = add_future_returns(df, horizons=[3, 5])

    assert "future_return_3d" in result.columns
    assert "future_return_5d" in result.columns
    assert result["future_return_3d"].tail(3).isna().all()
    assert result["future_return_5d"].tail(5).isna().all()
    assert result.loc[0, "future_return_3d"] == (13 / 10) - 1


def test_align_factor_values_adds_factor_prefixed_columns():
    df = _make_df(rows=30)
    registry = FactorRegistry([MaCrossValue(fast=3, slow=5)])

    result = align_factor_values(df, factor_names=["ma_cross_value"], factor_registry=registry)

    assert "factor:ma_cross_value" in result.columns
    assert len(result["factor:ma_cross_value"]) == len(df)
    assert result["factor:ma_cross_value"].iloc[:4].isna().all()
    assert result["factor:ma_cross_value"].iloc[10:].notna().any()


def test_build_alpha_dataset_generates_panel_for_3_tickers_30_days():
    dc = StubDataCenter()
    dc.add_frame("AAA", _make_df(rows=30, start="2024-01-02"))
    dc.add_frame("BBB", _make_df(rows=30, start="2024-01-02"))
    dc.add_frame("CCC", _make_df(rows=30, start="2024-01-02"))
    registry = FactorRegistry([MaCrossValue(fast=3, slow=5)])

    dataset = build_alpha_dataset(
        tickers=["AAA", "BBB", "CCC"],
        start_date="20240102",
        end_date="20240229",
        factors=["ma_cross_value"],
        horizons=[5, 20],
        data_center=dc,
        factor_registry=registry,
    )

    assert len(dataset) == 90
    assert set(dataset["ticker"]) == {"AAA", "BBB", "CCC"}
    assert "factor:ma_cross_value" in dataset.columns
    assert "future_return_5d" in dataset.columns
    assert "future_return_20d" in dataset.columns

    for ticker in ["AAA", "BBB", "CCC"]:
        one = dataset[dataset["ticker"] == ticker].reset_index(drop=True)
        assert one["future_return_5d"].tail(5).isna().all()
        assert one["future_return_20d"].tail(20).isna().all()


def test_build_alpha_dataset_marks_invalid_non_positive_volume_rows():
    dc = StubDataCenter()
    dc.add_frame("AAA", _make_df(rows=30, zero_volume_index=7))
    registry = FactorRegistry([MaCrossValue(fast=3, slow=5)])

    dataset = build_alpha_dataset(
        tickers=["AAA"],
        start_date="20240102",
        end_date="20240229",
        factors=["ma_cross_value"],
        horizons=[5],
        data_center=dc,
        factor_registry=registry,
    )

    invalid_rows = dataset.loc[dataset["is_valid_sample"] == False].reset_index(drop=True)
    assert len(invalid_rows) >= 1

    zero_volume_row = dataset.loc[dataset["volume"] <= 0].reset_index(drop=True)
    assert len(zero_volume_row) == 1
    assert zero_volume_row.loc[0, "is_valid_sample"] == False
    assert zero_volume_row.loc[0, "missing_reason"] == "non_positive_volume"
