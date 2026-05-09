from __future__ import annotations

import asyncio

import pandas as pd
from fastapi import APIRouter, HTTPException

from backend.api.config_endpoints import dc, load_config
from backend.core.engine import BacktestEngine
from backend.core.strategy import StrategyFactory

router = APIRouter(prefix="/api", tags=["backtest"])


def _resolve_strategy_label(strategy_name: str) -> str:
    return {
        "dual_ma": "双均线策略",
        "bollinger_bands": "布林带策略",
        "rsi_reversal": "RSI 反转策略",
    }.get(strategy_name, strategy_name)


async def fetch_stock_data_with_timeout(symbol: str, start_date: str, end_date: str, timeout: int = 20):
    return await asyncio.wait_for(
        asyncio.to_thread(dc.fetch_stock_data, symbol, start_date, end_date),
        timeout=timeout,
    )


def _extract_today_trades(logs: list[dict], end_date: str) -> list[dict]:
    today_str = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
    return [
        {"action": l.get("action"), "price": l.get("price"), "shares": l.get("shares")}
        for l in logs
        if str(l.get("execution_date", "")).startswith(today_str)
    ]


def _resolve_stock_name(df: pd.DataFrame, ticker: str) -> str:
    if not df.empty and "name" in df.columns:
        name = str(df["name"].iloc[0] or "").strip()
        if name:
            return name
    try:
        name = str(dc.get_stock_name(ticker) or "").strip()
        if name:
            return name
    except Exception:
        pass
    return ""


@router.get("/summary", summary="获取回测汇总")
async def get_summary(start_date: str, end_date: str):
    config = load_config()
    stock_pool = config.get("stock_pool", []) or []
    strategy_conf = config.get("strategy", {}) or {}
    strategy_name = strategy_conf.get("name", "bollinger_bands")
    strategy_params = strategy_conf.get("parameters", {}) or {}
    account_conf = config.get("account", {}) or {}

    if not stock_pool:
        return {"status": "success", "data": [], "data_source": "empty_pool", "fetch_note": "股票池为空"}

    rows = []
    source_tags = []
    notes = []
    errors = []
    for ticker in stock_pool:
        try:
            df = await fetch_stock_data_with_timeout(ticker, start_date, end_date)
            if df is None or df.empty:
                continue
            source_tags.append(str(df.attrs.get("data_source", "")))
            fetch_note = str(df.attrs.get("fetch_note", "")).strip()
            if fetch_note:
                notes.append(fetch_note)
            signal_df = StrategyFactory.generate_signals(df, strategy_name, strategy_params)
            engine = BacktestEngine(
                initial_cash=float(account_conf.get("initial_cash", 100000.0)),
                commission_rate=float(account_conf.get("commission_rate", 0.00025)),
                tax_rate=float(account_conf.get("tax_rate", 0.0005)),
            )
            result = engine.run(signal_df, ticker)
            metrics = result.get("metadata", {}) or {}
            logs = result.get("logs", []) or []
            stock_name = _resolve_stock_name(signal_df, ticker)
            rows.append({
                "ticker": ticker,
                "display_name": stock_name or ticker,
                "name": stock_name,
                "strategy": _resolve_strategy_label(strategy_name),
                "final_equity": metrics.get("final_equity", 0),
                "return_rate": metrics.get("total_return", 0),
                "trade_count": metrics.get("trade_count", 0),
                "today_trades": _extract_today_trades(logs, end_date),
            })
        except Exception as exc:
            errors.append(f"{ticker}: {exc}")
    if errors and not rows:
        raise HTTPException(status_code=500, detail={"message": "回测汇总生成失败", "errors": errors})
    unique_sources = {s for s in source_tags if s}
    if any("cache_plus" in s for s in unique_sources):
        data_source = "cache_partial"
    elif any(s in {"tushare", "remote"} for s in unique_sources):
        data_source = "partial_fetch"
    elif unique_sources == {"cache"}:
        data_source = "cache_first"
    else:
        data_source = next(iter(unique_sources), "unknown")
    fetch_note = "；".join(sorted(set(n for n in notes if n)))
    if errors:
        err_note = f"部分股票失败：{len(errors)} 只"
        fetch_note = f"{fetch_note}；{err_note}" if fetch_note else err_note
    return {"status": "success", "data": rows, "data_source": data_source, "fetch_note": fetch_note, "errors": errors}


@router.get("/detail/{ticker}", summary="获取个股回测详情")
async def get_stock_detail(ticker: str, start_date: str, end_date: str):
    config = load_config()
    strategy_conf = config.get("strategy", {}) or {}
    strategy_name = strategy_conf.get("name", "bollinger_bands")
    strategy_params = strategy_conf.get("parameters", {}) or {}
    account_conf = config.get("account", {}) or {}
    try:
        df = await fetch_stock_data_with_timeout(ticker, start_date, end_date)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"{ticker} 在指定区间无可用数据")
        signal_df = StrategyFactory.generate_signals(df, strategy_name, strategy_params)
        engine = BacktestEngine(
            initial_cash=float(account_conf.get("initial_cash", 100000.0)),
            commission_rate=float(account_conf.get("commission_rate", 0.00025)),
            tax_rate=float(account_conf.get("tax_rate", 0.0005)),
        )
        result = engine.run(signal_df, ticker)
        metrics = result.get("metadata", {}) or {}
        logs = result.get("logs", []) or []
        stock_name = _resolve_stock_name(signal_df, ticker)
        data_source = str(df.attrs.get("data_source", ""))
        fetch_note = str(df.attrs.get("fetch_note", "")).strip()
        klines = []
        for _, row in signal_df.iterrows():
            trade_signal = row.get("trade_signal", 0)
            klines.append({
                "date": row["date"].strftime("%Y-%m-%d") if pd.notna(row.get("date")) else "",
                "open": float(row.get("open", 0) or 0),
                "high": float(row.get("high", 0) or 0),
                "low": float(row.get("low", 0) or 0),
                "close": float(row.get("close", 0) or 0),
                "volume": float(row.get("volume", 0) or 0),
                "total_equity": float(row.get("total_equity", 0) or 0),
                "trade_signal": int(trade_signal) if pd.notna(trade_signal) else 0,
            })
        metadata = {
            **metrics,
            "ticker": ticker,
            "name": stock_name,
            "display_name": stock_name or ticker,
            "strategy_name": strategy_name,
            "strategy_label": _resolve_strategy_label(strategy_name),
            "data_source": data_source,
            "fetch_note": fetch_note,
            "start_date": start_date,
            "end_date": end_date,
        }
        return {"status": "success", "ticker": ticker, "name": stock_name, "display_name": stock_name or ticker, "metadata": metadata, "klines": klines, "logs": logs}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取 {ticker} 详情失败: {exc}")
