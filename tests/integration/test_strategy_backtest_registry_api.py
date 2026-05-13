from __future__ import annotations

import importlib

import pandas as pd


class StubPositionEngine:
    def __init__(self, *args, **kwargs):
        pass

    def run_with_positions(self, df, ticker, targets):
        out_df = df.copy()
        out_df["target_weight"] = [targets[0].target_weight for _ in range(len(out_df))]
        out_df["total_equity"] = [100000.0 + i * 1000 for i in range(len(out_df))]
        out_df["position_mode"] = ["target_weight" for _ in range(len(out_df))]
        return {
            "metadata": {
                "final_equity": float(out_df["total_equity"].iloc[-1]),
                "total_return": 0.12,
                "trade_count": 1,
                "position_mode": "target_weight",
                "active_target_weight": targets[0].target_weight,
            },
            "logs": [{"event": "rebalance", "ticker": ticker}],
            "data": out_df,
        }


def make_df(symbol: str) -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {"date": "2024-01-02", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 1000, "name": symbol},
            {"date": "2024-01-03", "open": 10, "high": 11, "low": 9, "close": 9.7, "volume": 1200, "name": symbol},
            {"date": "2024-01-04", "open": 9.7, "high": 10, "low": 9.4, "close": 9.5, "volume": 1500, "name": symbol},
            {"date": "2024-01-05", "open": 9.5, "high": 9.8, "low": 9.1, "close": 9.2, "volume": 1400, "name": symbol},
            {"date": "2024-01-08", "open": 9.2, "high": 9.4, "low": 8.9, "close": 9.0, "volume": 1600, "name": symbol},
            {"date": "2024-01-09", "open": 9.0, "high": 9.3, "low": 8.8, "close": 8.9, "volume": 1700, "name": symbol},
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_strategy_list_returns_registered_meta(client):
    response = client.get("/api/strategies")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert len(payload["strategies"]) >= 2  # multi_factor + demo
    assert payload["strategies"][0]["name"] == "multi_factor_target_weight"  # default = first


def test_strategy_detail_returns_registered_meta(client):
    response = client.get("/api/strategies/multi_factor_target_weight")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["strategy"]["name"] == "multi_factor_target_weight"
    assert len(payload["strategy"]["factor_names"]) >= 5  # multi-factor strategy
    assert "parameter_schema" in payload["strategy"]


def test_strategy_detail_unknown_strategy_returns_404(client):
    response = client.get("/api/strategies/unknown_demo")

    assert response.status_code == 404
    payload = response.json()
    assert "未知的新策略名称" in payload["detail"]


def test_strategy_backtest_single_ticker_returns_diagnostics(client, monkeypatch):
    backtest_endpoints = importlib.import_module("backend.api.backtest_endpoints")
    monkeypatch.setattr(
        backtest_endpoints,
        "load_config",
        lambda: {
            "stock_pool": ["CFG_ONLY"],
            "account": {"initial_cash": 100000, "commission_rate": 0.00025, "tax_rate": 0.0005},
        },
    )
    monkeypatch.setattr(backtest_endpoints, "BacktestEngine", StubPositionEngine)

    async def fake_fetch(symbol: str, start_date: str, end_date: str, timeout: int = 30):
        return make_df(symbol)

    monkeypatch.setattr(backtest_endpoints, "fetch_stock_data_with_timeout", fake_fetch)

    response = client.post(
        "/api/strategies/backtest",
        json={
            "strategy_name": "multi_factor_target_weight",
            "ticker": "AAA",
            "start_date": "20240101",
            "end_date": "20240131",
            "params": {"rsi_period": 5},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["mode"] == "single"
    assert payload["strategy_name"] == "multi_factor_target_weight"
    assert payload["selection_source"] == "ticker"
    assert payload["requested_tickers"] == ["AAA"]
    assert payload["resolved_tickers"] == ["AAA"]
    assert payload["count"] == 1
    assert len(payload["details"]) == 1
    assert payload["details"][0]["ticker"] == "AAA"
    assert payload["details"][0]["strategy_name"] == "multi_factor_target_weight"


def test_strategy_backtest_multi_ticker_deduplicates_and_summarizes(client, monkeypatch):
    backtest_endpoints = importlib.import_module("backend.api.backtest_endpoints")
    monkeypatch.setattr(
        backtest_endpoints,
        "load_config",
        lambda: {
            "stock_pool": ["CFG_ONLY"],
            "account": {"initial_cash": 100000, "commission_rate": 0.00025, "tax_rate": 0.0005},
        },
    )
    monkeypatch.setattr(backtest_endpoints, "BacktestEngine", StubPositionEngine)

    async def fake_fetch(symbol: str, start_date: str, end_date: str, timeout: int = 30):
        return make_df(symbol)

    monkeypatch.setattr(backtest_endpoints, "fetch_stock_data_with_timeout", fake_fetch)

    response = client.post(
        "/api/strategies/backtest",
        json={
            "strategy_name": "multi_factor_target_weight",
            "tickers": ["AAA", "BBB", "AAA"],
            "start_date": "20240101",
            "end_date": "20240131",
            "params": {"rsi_period": 5},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["selection_source"] == "tickers"
    assert payload["requested_tickers"] == ["AAA", "BBB", "AAA"]
    assert payload["resolved_tickers"] == ["AAA", "BBB"]
    assert payload["count"] == 2
    assert [row["ticker"] for row in payload["data"]] == ["AAA", "BBB"]
    assert [row["ticker"] for row in payload["details"]] == ["AAA", "BBB"]


def test_strategy_backtest_falls_back_to_config_stock_pool(client, monkeypatch):
    backtest_endpoints = importlib.import_module("backend.api.backtest_endpoints")
    monkeypatch.setattr(
        backtest_endpoints,
        "load_config",
        lambda: {
            "stock_pool": ["CFG_A", "CFG_B"],
            "account": {"initial_cash": 100000, "commission_rate": 0.00025, "tax_rate": 0.0005},
        },
    )
    monkeypatch.setattr(backtest_endpoints, "BacktestEngine", StubPositionEngine)

    async def fake_fetch(symbol: str, start_date: str, end_date: str, timeout: int = 30):
        return make_df(symbol)

    monkeypatch.setattr(backtest_endpoints, "fetch_stock_data_with_timeout", fake_fetch)

    response = client.post(
        "/api/strategies/backtest",
        json={
            "strategy_name": "multi_factor_target_weight",
            "start_date": "20240101",
            "end_date": "20240131",
            "params": {"rsi_period": 5},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["selection_source"] == "config_stock_pool"
    assert payload["requested_tickers"] == ["CFG_A", "CFG_B"]
    assert payload["resolved_tickers"] == ["CFG_A", "CFG_B"]
    assert [row["ticker"] for row in payload["data"]] == ["CFG_A", "CFG_B"]


def test_strategy_backtest_unknown_strategy_returns_400(client):
    response = client.post(
        "/api/strategies/backtest",
        json={
            "strategy_name": "unknown_demo",
            "ticker": "AAA",
            "start_date": "20240101",
            "end_date": "20240131",
            "params": {},
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert "未知的新策略名称" in payload["detail"]


def test_strategy_backtest_all_tickers_failed_returns_404(client, monkeypatch):
    backtest_endpoints = importlib.import_module("backend.api.backtest_endpoints")
    monkeypatch.setattr(
        backtest_endpoints,
        "load_config",
        lambda: {
            "stock_pool": ["AAA", "BBB"],
            "account": {"initial_cash": 100000, "commission_rate": 0.00025, "tax_rate": 0.0005},
        },
    )

    async def fake_fetch(symbol: str, start_date: str, end_date: str, timeout: int = 30):
        raise RuntimeError(f"boom:{symbol}")

    monkeypatch.setattr(backtest_endpoints, "fetch_stock_data_with_timeout", fake_fetch)

    response = client.post(
        "/api/strategies/backtest",
        json={
            "strategy_name": "multi_factor_target_weight",
            "start_date": "20240101",
            "end_date": "20240131",
            "params": {"rsi_period": 5},
        },
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"]["message"] == "全部 ticker 回测失败"
    assert [item["ticker"] for item in payload["detail"]["errors"]] == ["AAA", "BBB"]
    assert all(item["reason"] == "RuntimeError" for item in payload["detail"]["errors"])
