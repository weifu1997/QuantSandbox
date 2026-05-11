from __future__ import annotations

import importlib

import pandas as pd


class StubDataCenterSuccess:
    def fetch_stock_data(self, symbol: str, start_date: str, end_date: str):
        df = pd.DataFrame(
            [
                {"date": "2024-01-02", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 1000, "name": "福达股份"},
                {"date": "2024-01-03", "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 1200, "name": "福达股份"},
            ]
        )
        df["date"] = pd.to_datetime(df["date"])
        df.attrs["data_source"] = "cache_plus_remote"
        df.attrs["resolved_source"] = "tickflow"
        df.attrs["cache_miss"] = True
        df.attrs["fallback_trace"] = ["tushare:empty", "tickflow:success"]
        df.attrs["source_detail"] = "tushare:empty -> tickflow:success"
        df.attrs["fetch_note"] = "缓存未覆盖区间，自动拉远端"
        return df

    def get_stock_name(self, ticker: str) -> str:
        return "福达股份"


class StubDataCenterFailure:
    def fetch_stock_data(self, symbol: str, start_date: str, end_date: str):
        raise ValueError(
            f"⚠️ {symbol} 缓存与远端均未返回有效数据。cache_miss; "
            "trace=tushare:empty -> tickflow:cooldown -> akshare:error:RuntimeError"
        )

    def get_stock_name(self, ticker: str) -> str:
        return ""


class StubEngine:
    def __init__(self, *args, **kwargs):
        pass

    def run(self, signal_df, ticker):
        return {
            "metadata": {
                "final_equity": 12345.67,
                "total_return": 12.34,
                "trade_count": 2,
            },
            "logs": [],
        }


class StubStrategyFactory:
    @staticmethod
    def generate_signals(df, strategy_name, strategy_params):
        return df.copy()


def test_summary_preserves_fetch_stock_data_diagnostics_and_normalizes_ticker(client, monkeypatch):
    backtest_endpoints = importlib.import_module("backend.api.backtest_endpoints")
    monkeypatch.setattr(
        backtest_endpoints,
        "load_config",
        lambda: {
            "stock_pool": ["sh603166"],
            "strategy": {"name": "bollinger_bands", "parameters": {}},
            "account": {"initial_cash": 100000, "commission_rate": 0.00025, "tax_rate": 0.0005},
        },
    )
    monkeypatch.setattr(backtest_endpoints, "get_data_center", lambda: StubDataCenterSuccess())
    monkeypatch.setattr(backtest_endpoints, "BacktestEngine", StubEngine)
    monkeypatch.setattr(backtest_endpoints, "StrategyFactory", StubStrategyFactory)

    response = client.get("/api/summary", params={"start_date": "20240101", "end_date": "20240131"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["errors"] == []
    assert payload["data_source"] == "cache_partial"
    assert payload["fetch_note"] == "缓存未覆盖区间，自动拉远端"
    assert payload["data"][0]["ticker"] == "603166"
    assert payload["data"][0]["display_name"] == "福达股份"


def test_summary_errors_include_detailed_fetch_trace(client, monkeypatch):
    backtest_endpoints = importlib.import_module("backend.api.backtest_endpoints")
    monkeypatch.setattr(
        backtest_endpoints,
        "load_config",
        lambda: {
            "stock_pool": ["603166"],
            "strategy": {"name": "bollinger_bands", "parameters": {}},
            "account": {"initial_cash": 100000, "commission_rate": 0.00025, "tax_rate": 0.0005},
        },
    )
    monkeypatch.setattr(backtest_endpoints, "get_data_center", lambda: StubDataCenterFailure())

    response = client.get("/api/summary", params={"start_date": "20240101", "end_date": "20240131"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"] == []
    assert payload["data_source"] == "unavailable"
    assert payload["fetch_note"] == "全部股票获取失败"
    assert len(payload["errors"]) == 1

    err = payload["errors"][0]
    assert err["ticker"] == "603166"
    assert err["reason"] == "ValueError"
    assert "cache_miss" in err["message"]
    assert "tushare:empty" in err["message"]
    assert "tickflow:cooldown" in err["message"]
    assert "akshare:error:RuntimeError" in err["message"]
