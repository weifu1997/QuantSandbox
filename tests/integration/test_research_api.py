import pandas as pd

from backend.api.config_endpoints import get_data_center


def _patch_data_center(monkeypatch, rows: int = 80):
    class StubDataCenter:
        def fetch_stock_data(self, symbol: str, start_date: str, end_date: str):
            dates = pd.date_range("2024-01-02", periods=rows, freq="B")
            offset = int(symbol[-1]) if symbol[-1].isdigit() else 1
            close = pd.Series([10 + offset + i for i in range(rows)], dtype="float64")
            volume = pd.Series([1_000_000 + offset * 1000] * rows, dtype="float64")
            return pd.DataFrame(
                {
                    "date": dates,
                    "open": close - 0.2,
                    "high": close + 0.5,
                    "low": close - 0.5,
                    "close": close,
                    "volume": volume,
                    "amount": close * volume,
                    "pe_ttm": pd.Series([10 + (i % 5) for i in range(rows)], dtype="float64"),
                    "pb": pd.Series([1 + (i % 3) * 0.1 for i in range(rows)], dtype="float64"),
                    "dividend_yield": pd.Series([2 + (i % 2) * 0.1 for i in range(rows)], dtype="float64"),
                    "name": [symbol] * rows,
                }
            )

    stub = StubDataCenter()
    get_data_center.cache_clear()
    monkeypatch.setattr("backend.api.config_endpoints.get_data_center", lambda: stub)
    monkeypatch.setattr("backend.api.research_endpoints.get_data_center", lambda: stub)


def test_research_dataset_build_api(client, monkeypatch):
    _patch_data_center(monkeypatch)

    response = client.post(
        "/api/research/dataset/build",
        json={
            "tickers": ["AAA1", "BBB2", "CCC3"],
            "start_date": "20240102",
            "end_date": "20240329",
            "factors": ["momentum_20d", "pe_ttm"],
            "horizons": [5, 20],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["rows"] > 0
    assert body["data"]["tickers"] == ["AAA1", "BBB2", "CCC3"]
    assert set(body["data"]["factors"]) == {"momentum_20d", "pe_ttm"}


def test_research_factor_ic_api(client, monkeypatch):
    _patch_data_center(monkeypatch)

    response = client.post(
        "/api/research/factor/ic",
        json={
            "tickers": ["AAA1", "BBB2", "CCC3", "DDD4", "EEE5", "FFF6", "GGG7", "HHH8", "III9", "JJJ0", "KKK1", "LLL2"],
            "start_date": "20240102",
            "end_date": "20240329",
            "factor_name": "momentum_20d",
            "horizons": [5],
            "min_cross_section": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["factor_name"] == "momentum_20d"
    assert "5" in body["data"]["horizons"]
    assert "ic_mean" in body["data"]["horizons"]["5"]


def test_research_group_backtest_api(client, monkeypatch):
    _patch_data_center(monkeypatch)

    response = client.post(
        "/api/research/factor/group-backtest",
        json={
            "tickers": ["AAA1", "BBB2", "CCC3", "DDD4", "EEE5", "FFF6", "GGG7", "HHH8", "III9", "JJJ0"],
            "start_date": "20240102",
            "end_date": "20240329",
            "factor_name": "momentum_20d",
            "horizon": 20,
            "groups": 5,
            "rebalance_frequency": "D",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["groups"] == 5
    assert "Q1" in body["data"]["group_return_by_group"]
    assert "Q5" in body["data"]["equity_curve_by_group"]


def test_research_topn_backtest_api(client, monkeypatch):
    _patch_data_center(monkeypatch)

    response = client.post(
        "/api/research/topn-backtest",
        json={
            "tickers": ["AAA1", "BBB2", "CCC3", "DDD4", "EEE5", "FFF6", "GGG7", "HHH8", "III9", "JJJ0"],
            "start_date": "20240102",
            "end_date": "20240329",
            "factor_name": "momentum_20d",
            "horizon": 20,
            "top_n": 5,
            "rebalance_frequency": "W",
            "weighting": "equal",
            "transaction_cost_bps": 10,
            "benchmark": "equal_weight_universe",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["top_n"] == 5
    assert "total_return" in body["data"]
    assert isinstance(body["data"]["equity_curve"], list)


def test_research_report_api_json(client, monkeypatch):
    _patch_data_center(monkeypatch)

    response = client.post(
        "/api/research/report",
        json={
            "tickers": ["AAA1", "BBB2", "CCC3", "DDD4", "EEE5", "FFF6", "GGG7", "HHH8", "III9", "JJJ0", "KKK1", "LLL2"],
            "start_date": "20240102",
            "end_date": "20240531",
            "factors": ["momentum_20d", "pe_ttm"],
            "horizons": [20],
            "min_cross_section": 5,
            "groups": 5,
            "rebalance_frequency": "W",
            "top_n": 5,
            "weighting": "equal",
            "transaction_cost_bps": 10,
            "benchmark": "equal_weight_universe",
            "output_format": "json",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["title"] == "Alpha Research Report"
    assert body["data"]["config"]["factors"] == ["momentum_20d", "pe_ttm"]
    assert len(body["data"]["factor_summaries"]) == 2
    assert "momentum_20d" in body["data"]["factor_details"]
    assert "recommended_factors" in body["data"]["conclusion"]


def test_research_report_api_markdown(client, monkeypatch):
    _patch_data_center(monkeypatch)

    response = client.post(
        "/api/research/report",
        json={
            "tickers": ["AAA1", "BBB2", "CCC3", "DDD4", "EEE5", "FFF6", "GGG7", "HHH8", "III9", "JJJ0", "KKK1", "LLL2"],
            "start_date": "20240102",
            "end_date": "20240531",
            "factors": ["momentum_20d"],
            "horizons": [20],
            "min_cross_section": 5,
            "groups": 5,
            "rebalance_frequency": "W",
            "top_n": 5,
            "weighting": "equal",
            "transaction_cost_bps": 10,
            "benchmark": "equal_weight_universe",
            "output_format": "markdown",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["output_format"] == "markdown"
    assert "# Alpha Research Report" in body["data"]["markdown"]
    assert "## 因子总览表" in body["data"]["markdown"]
