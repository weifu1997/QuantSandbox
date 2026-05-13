from __future__ import annotations

import asyncio
import datetime
import logging

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.api.config_endpoints import get_data_center, load_config
from backend.api.error_helpers import log_and_raise_http
from backend.core.engine import BacktestEngine
from backend.core.strategies.registry import get_strategy_registry
from backend.core.strategy import PositionTarget
from backend.core.task_store import TaskStore, TaskStatus
from backend.services.summary_async_service import SummaryAsyncService

router = APIRouter(prefix="/api", tags=["backtest"])
logger = logging.getLogger(__name__)


class StrategyBacktestRequest(BaseModel):
    strategy_name: str = Field(..., description="当前最小版本通过 registry 路由新策略")
    ticker: str | None = Field(default=None, min_length=1)
    tickers: list[str] = Field(default_factory=list)
    start_date: str = Field(..., min_length=8, max_length=8)
    end_date: str = Field(..., min_length=8, max_length=8)
    params: dict = Field(default_factory=dict)


def _resolve_strategy_label(strategy_name: str) -> str:
    return {
        "target_weight_demo": "目标仓位示例策略（SMOKE ONLY）",
        "multi_factor_target_weight": "多因子综合仓位策略",
    }.get(strategy_name, strategy_name)


@router.get("/strategies", summary="列出可用新策略")
def list_new_strategies():
    registry = get_strategy_registry()
    return {
        "status": "success",
        "strategies": registry.list_meta(),
    }


@router.get("/strategies/{strategy_name}", summary="获取单个新策略详情")
def get_strategy_detail(strategy_name: str):
    registry = get_strategy_registry()
    try:
        strategy_cls = registry.get(strategy_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    strategy = strategy_cls()
    return {
        "status": "success",
        "strategy": strategy.meta(),
    }


async def fetch_stock_data_with_timeout(symbol: str, start_date: str, end_date: str, timeout: int = 20):
    dc = get_data_center()
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(dc.fetch_stock_data, symbol, start_date, end_date),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        source_status = dc.get_source_status() if hasattr(dc, "get_source_status") else {}
        source_fail_state = source_status.get("source_fail_state", {}) if isinstance(source_status, dict) else {}
        compact_sources = {
            source: {
                "fail_count": info.get("fail_count"),
                "in_cooldown": info.get("in_cooldown"),
                "last_status": info.get("last_status"),
                "last_error": info.get("last_error"),
            }
            for source, info in source_fail_state.items()
        }
        raise TimeoutError(
            f"{symbol} fetch timed out after {timeout}s; "
            f"stage=single_ticker_fetch_envelope; cache_miss=unknown; sources={compact_sources}"
        ) from exc


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
        name = str(get_data_center().get_stock_name(ticker) or "").strip()
        if name:
            return name
    except Exception:
        logger.warning("failed to resolve stock name", extra={"ticker": ticker}, exc_info=True)
    return ""


def _normalize_ticker_output(ticker: str) -> str:
    value = str(ticker or "").strip()
    lowered = value.lower()
    for prefix in ("sh", "sz", "bj"):
        if lowered.startswith(prefix) and len(value) > len(prefix):
            return value[len(prefix):]
    return value


def _extract_fetch_diagnostics(df: pd.DataFrame) -> dict:
    return {
        "data_source": str(df.attrs.get("data_source", "") or ""),
        "resolved_source": str(df.attrs.get("resolved_source", "") or ""),
        "cache_miss": bool(df.attrs.get("cache_miss", False)),
        "fallback_trace": list(df.attrs.get("fallback_trace", []) or []),
        "source_detail": str(df.attrs.get("source_detail", "") or ""),
        "fetch_note": str(df.attrs.get("fetch_note", "") or "").strip(),
    }


def _build_empty_error(ticker: str) -> dict:
    return {
        "ticker": ticker,
        "reason": "empty_dataframe",
        "message": f"{ticker} 在指定区间无可用数据",
        "data_source": "",
        "resolved_source": "",
        "cache_miss": None,
        "fallback_trace": [],
        "source_detail": "",
    }


def _build_exception_error(ticker: str, exc: Exception) -> dict:
    return {
        "ticker": ticker,
        "reason": type(exc).__name__,
        "message": str(exc),
        "data_source": "",
        "resolved_source": "",
        "cache_miss": None,
        "fallback_trace": [],
        "source_detail": "",
    }


def _resolve_requested_tickers(ticker: str | None, tickers: list[str], config: dict) -> tuple[str, list[str], list[str]]:
    requested_tickers: list[str] = []
    if ticker:
        requested_tickers.append(ticker)
    requested_tickers.extend([value for value in tickers if str(value or '').strip()])

    configured_stock_pool = config.get("stock_pool", []) or []
    selection_source = "config_stock_pool"
    if ticker:
        selection_source = "ticker"
    elif tickers:
        selection_source = "tickers"
    if not requested_tickers and configured_stock_pool:
        requested_tickers.extend(configured_stock_pool)

    requested_tickers = [str(value).strip() for value in requested_tickers if str(value).strip()]
    resolved_tickers = list(dict.fromkeys(requested_tickers))
    return selection_source, requested_tickers, resolved_tickers


@router.get("/summary", summary="获取回测汇总")
async def get_summary(start_date: str, end_date: str):
    try:
        return await SummaryAsyncService().build_summary(start_date, end_date)
    except Exception as exc:
        log_and_raise_http(
            500,
            "回测汇总生成失败",
            exc=exc,
            context={"start_date": start_date, "end_date": end_date},
        )


@router.post("/summary/tasks", summary="提交回测汇总任务")
def submit_summary_task(start_date: str, end_date: str):
    return {"status": "accepted", "data": SummaryAsyncService().submit(start_date, end_date)}


@router.get("/summary/tasks/{task_id}", summary="查询回测汇总任务")
def get_summary_task(task_id: str):
    data = SummaryAsyncService().get_task_result(task_id)
    if data is None:
        raise HTTPException(status_code=404, detail={"message": f"未找到任务 {task_id}"})
    return {"status": "success", "data": data}


@router.post("/strategies/backtest", summary="运行新策略回测（最小骨架）")
async def run_strategy_backtest(payload: StrategyBacktestRequest):
    registry = get_strategy_registry()
    try:
        strategy = registry.create(payload.strategy_name, payload.params or {})
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    config = load_config()
    selection_source, requested_tickers, tickers = _resolve_requested_tickers(payload.ticker, payload.tickers, config)
    if not tickers:
        raise HTTPException(status_code=400, detail="至少提供 ticker/tickers，或在 config.yaml 中配置 stock_pool")

    account_conf = config.get("account", {}) or {}
    rows = []
    all_errors = []
    try:
        for ticker in tickers:
            try:
                df = await fetch_stock_data_with_timeout(ticker, payload.start_date, payload.end_date, timeout=30)
                if df is None or df.empty:
                    raise HTTPException(status_code=404, detail=f"{ticker} 在指定区间无可用数据")

                targets = strategy.generate_targets(df, ticker)
                engine = BacktestEngine(
                    initial_cash=float(account_conf.get("initial_cash", 100000.0)),
                    commission_rate=float(account_conf.get("commission_rate", 0.00025)),
                    tax_rate=float(account_conf.get("tax_rate", 0.0005)),
                )
                result = engine.run_with_positions(df, ticker, targets)
                metrics = result.get("metadata", {}) or {}
                logs = result.get("logs", []) or []
                result_df = result.get("data")
                stock_name = _resolve_stock_name(df, ticker)

                klines = []
                if isinstance(result_df, pd.DataFrame):
                    for _, row in result_df.iterrows():
                        klines.append({
                            "date": row["date"].strftime("%Y-%m-%d") if pd.notna(row.get("date")) else "",
                            "open": float(row.get("open", 0) or 0),
                            "high": float(row.get("high", 0) or 0),
                            "low": float(row.get("low", 0) or 0),
                            "close": float(row.get("close", 0) or 0),
                            "target_weight": float(row.get("target_weight", 0) or 0),
                            "total_equity": float(row.get("total_equity", 0) or 0),
                            "position_mode": str(row.get("position_mode", "") or ""),
                        })

                rows.append({
                    "ticker": ticker,
                    "name": stock_name,
                    "display_name": stock_name or ticker,
                    "strategy_name": payload.strategy_name,
                    "strategy_meta": strategy.meta(),
                    "targets": [target.to_dict() for target in targets],
                    "metadata": {
                        **metrics,
                        "ticker": ticker,
                        "name": stock_name,
                        "display_name": stock_name or ticker,
                        "start_date": payload.start_date,
                        "end_date": payload.end_date,
                    },
                    "klines": klines,
                    "logs": logs,
                })
            except HTTPException as exc:
                all_errors.append({"ticker": ticker, "reason": "HTTPException", "message": str(exc.detail)})
            except Exception as exc:
                all_errors.append(_build_exception_error(ticker, exc))

        if not rows:
            raise HTTPException(status_code=404, detail={"message": "全部 ticker 回测失败", "errors": all_errors})

        if len(rows) == 1:
            # 单标的也返回统一 envelope（与多标的相同结构）
            return {
                "status": "success",
                "mode": "single",
                "strategy_name": payload.strategy_name,
                "strategy_meta": strategy.meta(),
                "selection_source": selection_source,
                "requested_tickers": requested_tickers,
                "resolved_tickers": tickers,
                "start_date": payload.start_date,
                "end_date": payload.end_date,
                "count": 1,
                "data": [{
                    "ticker": rows[0].get("ticker"),
                    "display_name": rows[0].get("display_name"),
                    "name": rows[0].get("name"),
                    "strategy": _resolve_strategy_label(payload.strategy_name),
                    "final_equity": rows[0]["metadata"].get("final_equity", 0),
                    "return_rate": rows[0]["metadata"].get("total_return", 0),
                    "position_return": rows[0]["metadata"].get("position_return", 0),
                    "avg_deployed_ratio": rows[0]["metadata"].get("avg_deployed_ratio", 0),
                    "trade_count": rows[0]["metadata"].get("trade_count", 0),
                    "position_mode": rows[0]["metadata"].get("position_mode", ""),
                    "active_target_weight": rows[0]["metadata"].get("active_target_weight", 0),
                }],
                "details": rows,
                "errors": all_errors,
            }

        summary_rows = []
        for row in rows:
            metadata = row.get("metadata", {}) or {}
            summary_rows.append({
                "ticker": row.get("ticker"),
                "display_name": row.get("display_name"),
                "name": row.get("name"),
                "strategy": _resolve_strategy_label(payload.strategy_name),
                "final_equity": metadata.get("final_equity", 0),
                "return_rate": metadata.get("total_return", 0),
                "position_return": metadata.get("position_return", 0),
                "avg_deployed_ratio": metadata.get("avg_deployed_ratio", 0),
                "trade_count": metadata.get("trade_count", 0),
                "position_mode": metadata.get("position_mode", ""),
                "active_target_weight": metadata.get("active_target_weight", 0),
            })

        return {
            "status": "success",
            "mode": "multi",
            "strategy_name": payload.strategy_name,
            "strategy_meta": strategy.meta(),
            "selection_source": selection_source,
            "requested_tickers": requested_tickers,
            "resolved_tickers": tickers,
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "count": len(rows),
            "data": summary_rows,
            "details": rows,
            "errors": all_errors,
        }
    except HTTPException:
        raise
    except Exception as exc:
        log_and_raise_http(
            500,
            "运行新策略回测失败",
            exc=exc,
            context={
                "tickers": tickers,
                "start_date": payload.start_date,
                "end_date": payload.end_date,
                "strategy_name": payload.strategy_name,
                "params": payload.params,
            },
        )


@router.get("/detail/{ticker}", summary="获取个股回测详情")
async def get_stock_detail(ticker: str, start_date: str, end_date: str):
    config = load_config()
    strategy_conf = config.get("strategy", {}) or {}
    strategy_name = strategy_conf.get("name", "multi_factor_target_weight")
    strategy_params = strategy_conf.get("parameters", {}) or {}
    account_conf = config.get("account", {}) or {}

    # 使用新 registry 路由策略
    registry = get_strategy_registry()
    try:
        registry.get(strategy_name)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        df = await fetch_stock_data_with_timeout(ticker, start_date, end_date)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"{ticker} 在指定区间无可用数据")

        strategy = registry.create(strategy_name, strategy_params)
        targets = strategy.generate_targets(df, ticker)
        engine = BacktestEngine(
            initial_cash=float(account_conf.get("initial_cash", 100000.0)),
            commission_rate=float(account_conf.get("commission_rate", 0.00025)),
            tax_rate=float(account_conf.get("tax_rate", 0.0005)),
        )
        result = engine.run_with_positions(df, ticker, targets)
        metrics = result.get("metadata", {}) or {}
        logs = result.get("logs", []) or []
        stock_name = _resolve_stock_name(df, ticker)
        diag = _extract_fetch_diagnostics(df)
        data_source = diag["data_source"]
        fetch_note = diag["fetch_note"]

        klines = []
        result_df = result.get("data")
        if isinstance(result_df, pd.DataFrame):
            for _, row in result_df.iterrows():
                klines.append({
                    "date": row["date"].strftime("%Y-%m-%d") if pd.notna(row.get("date")) else "",
                    "open": float(row.get("open", 0) or 0),
                    "high": float(row.get("high", 0) or 0),
                    "low": float(row.get("low", 0) or 0),
                    "close": float(row.get("close", 0) or 0),
                    "volume": float(row.get("volume", 0) or 0),
                    "total_equity": float(row.get("total_equity", 0) or 0),
                    "target_weight": float(row.get("target_weight", 0) or 0),
                    "position_mode": str(row.get("position_mode", "") or ""),
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
        return {
            "status": "success",
            "ticker": ticker,
            "name": stock_name,
            "display_name": stock_name or ticker,
            "metadata": metadata,
            "klines": klines,
            "logs": logs,
        }
    except HTTPException:
        raise
    except Exception as exc:
        log_and_raise_http(
            500,
            f"获取 {ticker} 详情失败",
            exc=exc,
            context={"ticker": ticker, "start_date": start_date, "end_date": end_date, "strategy_name": strategy_name},
        )


# ---------------------------------------------------------------------------
# D-5 Third Batch: Portfolio Backtest API
# ---------------------------------------------------------------------------

class PortfolioBacktestRequest(BaseModel):
    strategy_name: str = Field(..., description="通过 registry 路由的策略名")
    tickers: list[str] = Field(..., min_length=1, description="标的列表")
    start_date: str = Field(..., min_length=8, max_length=8)
    end_date: str = Field(..., min_length=8, max_length=8)
    params: dict = Field(default_factory=dict, description="策略参数")
    initial_cash: float = Field(default=100000.0, ge=1, description="初始资金")
    commission_rate: float = Field(default=0.00025, ge=0, description="佣金费率")
    tax_rate: float = Field(default=0.0005, ge=0, description="印花税率")
    slippage_rate: float = Field(default=0.0005, ge=0, description="滑点率")


@router.post("/strategies/portfolio/backtest", summary="运行组合级回测")
async def run_portfolio_backtest(payload: PortfolioBacktestRequest):
    """多标的组合级真实回测：共享现金池，先卖后买，含费用和约束。"""
    # 1. 校验策略
    registry = get_strategy_registry()
    try:
        strategy_cls = registry.get(payload.strategy_name)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 2. 拉取各标的行情
    frames_by_ticker: dict[str, pd.DataFrame] = {}
    fetch_errors: list[dict] = []
    for ticker in payload.tickers:
        try:
            df = await fetch_stock_data_with_timeout(ticker, payload.start_date, payload.end_date, timeout=30)
            if df is None or df.empty:
                fetch_errors.append({"ticker": ticker, "reason": "empty_data"})
                continue
            frames_by_ticker[ticker] = df.reset_index(drop=True)
        except Exception as exc:
            fetch_errors.append({"ticker": ticker, "reason": type(exc).__name__, "message": str(exc)})

    if not frames_by_ticker:
        raise HTTPException(status_code=404, detail={
            "message": "全部标的组合回测数据获取失败",
            "errors": fetch_errors,
        })

    # 3. 运行组合回测
    engine = BacktestEngine(
        initial_cash=payload.initial_cash,
        commission_rate=payload.commission_rate,
        tax_rate=payload.tax_rate,
        slippage_rate=payload.slippage_rate,
    )
    result = engine.run_portfolio(frames_by_ticker, strategy_cls, payload.params or {})

    # 4. 构建返回
    strategy = strategy_cls(payload.params or {})
    return {
        "status": "success",
        "strategy_name": payload.strategy_name,
        "strategy_meta": strategy.meta(),
        "ticker_count": len(frames_by_ticker),
        "resolved_tickers": list(frames_by_ticker.keys()),
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "portfolio_metrics": result["portfolio_metrics"],
        "portfolio_equity": result["portfolio_equity"],
        "per_ticker": {
            ticker: {
                "metadata": info["metadata"],
                "equity": info["equity"],
            }
            for ticker, info in result["per_ticker"].items()
        },
        "logs": result["logs"],
        "fetch_errors": fetch_errors if fetch_errors else None,
    }
