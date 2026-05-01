import os
import asyncio
import tempfile
import yaml
import pandas as pd
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.core.data_center import DataCenter
from backend.core.engine import BacktestEngine
from backend.core.strategy import StrategyFactory
from backend.integrations.mx_search_adapter import run_query as run_mx_search_query
from backend.integrations.mx_data_adapter import run_query as run_mx_data_query
from backend.integrations.mx_xuangu_adapter import run_query as run_mx_xuangu_query
from backend.integrations.mx_moni_adapter import run_query as run_mx_moni_query

app = FastAPI(title="Quant Simulate System API")

# 配置 CORS，允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 实例化数据中心
dc = DataCenter()

class ConfigUpdateRequest(BaseModel):
    stock_pool: list[str] | None = None
    strategy_name: str | None = None
    strategy_parameters: dict | None = None


def load_config():
    """加载 YAML 配置文件"""
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../config.yaml"))
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@app.get("/api/config", summary="获取回测配置")
def get_config():
    config = load_config()
    return {
        "status": "success",
        "stock_pool": config.get("stock_pool", []),
        "strategy": config.get("strategy", {}),
    }


@app.post("/api/config", summary="更新回测配置")
def update_config(payload: ConfigUpdateRequest):
    config = load_config()
    if payload.stock_pool is not None:
        config["stock_pool"] = payload.stock_pool
    if payload.strategy_name is not None:
        config.setdefault("strategy", {})["name"] = payload.strategy_name
    if payload.strategy_parameters is not None:
        config.setdefault("strategy", {})["parameters"] = payload.strategy_parameters
    save_config(config)
    return {"status": "success"}

def clean_nan(df: pd.DataFrame) -> list:
    """清理 DataFrame 中的 NaN 值，防止 JSON 序列化报错"""
    return df.fillna("").to_dict(orient="records")


def save_config(config: dict):
    """原子写回配置文件"""
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../config.yaml"))
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="config_", suffix=".yaml", dir=os.path.dirname(config_path))
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
        os.replace(tmp_path, config_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


class ConfigUpdateRequest(BaseModel):
    stock_pool: list[str] | None = None
    strategy_name: str | None = None
    strategy_parameters: dict | None = None

@app.get("/api/meta", summary="获取系统元信息")
def get_meta():
    latest_trade_date = dc.get_latest_trade_date()
    return {
        "status": "success",
        "latest_trade_date": latest_trade_date,
        "data_source_enabled": bool(getattr(dc, "tushare_base_url", "") and getattr(dc, "tushare_token", "")),
    }

async def fetch_stock_data_with_timeout(symbol: str, start_date: str, end_date: str, timeout: int = 20):
    """给单只股票的数据抓取加超时，避免一只票拖死整个接口"""
    return await asyncio.wait_for(
        asyncio.to_thread(dc.fetch_stock_data, symbol, start_date, end_date),
        timeout=timeout,
    )

@app.get("/api/summary", summary="获取大盘总览数据")
async def get_summary(start_date: str = "20240101", end_date: str = "20240201"):
    config = load_config()
    pool = config['stock_pool']

    cached_tickers = [ticker for ticker in pool if dc.has_cached_data(ticker)]
    cold_tickers = [ticker for ticker in pool if ticker not in cached_tickers]

    def _build_result(ticker: str, raw_data: pd.DataFrame, stock_name: str, data_source: str, fetch_note: str):
        if raw_data is None or raw_data.empty:
            return None
        df_signals = StrategyFactory.generate_signals(
            raw_data,
            config['strategy']['name'],
            config['strategy']['parameters']
        )
        mask = (df_signals['date'] >= pd.to_datetime(start_date)) & (df_signals['date'] <= pd.to_datetime(end_date))
        df_slice = df_signals.loc[mask].copy().reset_index(drop=True)
        if df_slice.empty:
            return None
        engine = BacktestEngine(
            initial_cash=config['account']['initial_cash'],
            commission_rate=config['account']['commission_rate'],
            tax_rate=config['account']['tax_rate']
        )
        res = engine.run(df_slice, ticker)
        meta = res['metadata']
        return {
            "ticker": ticker,
            "name": stock_name,
            "strategy": config['strategy']['name'],
            "final_equity": meta['final_equity'],
            "return_rate": meta['total_return'],
            "trade_count": meta['trade_count'],
            "data_source": data_source,
            "fetch_note": fetch_note,
        }

    async def _process_cached(ticker: str):
        try:
            cache_record = dc._get_cache_record(ticker)
            if not cache_record or not os.path.exists(cache_record["file_path"]):
                return None

            def _load_and_build():
                raw_data = dc._load_cache_df(cache_record["file_path"])
                if raw_data.empty:
                    return None
                stock_name = str(raw_data["name"].iloc[0] or "") if "name" in raw_data.columns else ""
                return _build_result(ticker, raw_data, stock_name, "cache", "缓存优先：summary 未触发远端补齐")

            return await asyncio.to_thread(_load_and_build)
        except Exception as e:
            print(f"⚠️ 处理 {ticker} 失败: {e}")
            return None

    async def _process_remote(ticker: str):
        try:
            raw_data = await fetch_stock_data_with_timeout(ticker, start_date="20230101", end_date=end_date, timeout=10)

            def _build_remote():
                stock_name = str(raw_data["name"].iloc[0] or "") if (not raw_data.empty and "name" in raw_data.columns) else ""
                data_source = raw_data.attrs.get("data_source", "remote") if hasattr(raw_data, "attrs") else "remote"
                fetch_note = raw_data.attrs.get("fetch_note", "") if hasattr(raw_data, "attrs") else ""
                return _build_result(ticker, raw_data, stock_name, data_source, fetch_note)

            return await asyncio.to_thread(_build_remote)
        except Exception as e:
            print(f"⚠️ 处理 {ticker} 失败: {e}")
            return None

    async def _collect(tickers, budget_sec: float, handler):
        tasks = [asyncio.create_task(handler(t)) for t in tickers]
        if not tasks:
            return [], False
        done, pending = await asyncio.wait(tasks, timeout=budget_sec)
        rows = []
        for task in done:
            try:
                row = task.result()
                if row is not None:
                    rows.append(row)
            except Exception:
                continue
        return rows, bool(pending)

    cached_rows, cached_pending = await _collect(cached_tickers, 8, _process_cached)
    if cached_rows:
        if cold_tickers:
            asyncio.create_task(_collect(cold_tickers, 6, _process_remote))
        return {
            "status": "success",
            "data": cached_rows,
            "data_source": "cache_first" if not cached_pending else "cache_partial",
            "fetch_note": "短区间优先：缓存结果已返回，冷票继续后台补齐" if cached_pending else "短区间优先：缓存结果已返回",
        }

    remote_rows, remote_pending = await _collect(pool, 12, _process_remote)
    return {
        "status": "success",
        "data": remote_rows,
        "data_source": "full_fetch" if not remote_pending else "partial_fetch",
        "fetch_note": "短区间优先：数据补齐中" if remote_pending else "全量结果已返回",
    }


@app.post("/api/mx/search", summary="妙想资讯搜索查询")
def mx_search_query(payload: dict):
    query = str(payload.get("query", "")).strip()
    if not query:
        raise HTTPException(status_code=400, detail="query 不能为空")
    try:
        result = run_mx_search_query(query)
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mx/data", summary="妙想金融数据查询")
def mx_data_query(payload: dict):
    query = str(payload.get("query", "")).strip()
    if not query:
        raise HTTPException(status_code=400, detail="query 不能为空")
    try:
        result = run_mx_data_query(query)
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mx/xuangu", summary="妙想智能选股查询")
def mx_xuangu_query(payload: dict):
    query = str(payload.get("query", "")).strip()
    if not query:
        raise HTTPException(status_code=400, detail="query 不能为空")
    try:
        result = run_mx_xuangu_query(query)
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mx/moni", summary="妙想模拟组合查询")
def mx_moni_query(payload: dict):
    query = str(payload.get("query", "")).strip()
    if not query:
        raise HTTPException(status_code=400, detail="query 不能为空")
    try:
        result = run_mx_moni_query(query)
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/detail/{ticker}", summary="获取单票详细数据")
async def get_detail(ticker: str, start_date: str = "20240101", end_date: str = "20240131"):
    config = load_config()

    try:
        cache_record = dc._get_cache_record(ticker)
        if cache_record and os.path.exists(cache_record["file_path"]):
            cached_data = dc._load_cache_df(cache_record["file_path"])
            if not cached_data.empty:
                stock_name = ""
                if "name" in cached_data.columns:
                    stock_name = str(cached_data["name"].iloc[0] or "")

                effective_end = min(end_date, cache_record.get("end_date", end_date))
                df_signals = StrategyFactory.generate_signals(
                    cached_data,
                    config['strategy']['name'],
                    config['strategy']['parameters']
                )
                mask = (df_signals['date'] >= pd.to_datetime(start_date)) &                        (df_signals['date'] <= pd.to_datetime(effective_end))
                df_slice = df_signals.loc[mask].copy().reset_index(drop=True)
                if not df_slice.empty:
                    engine = BacktestEngine(
                        initial_cash=config['account']['initial_cash'],
                        commission_rate=config['account']['commission_rate'],
                        tax_rate=config['account']['tax_rate']
                    )
                    res = engine.run(df_slice, ticker)
                    res['data']['date'] = res['data']['date'].dt.strftime('%Y-%m-%d')
                    return {
                        "status": "success",
                        "name": stock_name,
                        "metadata": res['metadata'],
                        "klines": clean_nan(res['data']),
                        "logs": res['logs'],
                        "data_source": "cache",
                    }

        raw_data = await fetch_stock_data_with_timeout(ticker, start_date="20230101", end_date=end_date, timeout=10)

        stock_name = ""
        if not raw_data.empty and "name" in raw_data.columns:
            stock_name = str(raw_data["name"].iloc[0] or "")

        df_signals = StrategyFactory.generate_signals(
            raw_data,
            config['strategy']['name'],
            config['strategy']['parameters']
        )

        mask = (df_signals['date'] >= pd.to_datetime(start_date)) &                (df_signals['date'] <= pd.to_datetime(end_date))
        df_slice = df_signals.loc[mask].copy().reset_index(drop=True)

        if df_slice.empty:
            raise ValueError("该时间区间内没有交易数据")

        engine = BacktestEngine(
            initial_cash=config['account']['initial_cash'],
            commission_rate=config['account']['commission_rate'],
            tax_rate=config['account']['tax_rate']
        )
        res = engine.run(df_slice, ticker)

        res['data']['date'] = res['data']['date'].dt.strftime('%Y-%m-%d')

        return {
            "status": "success",
            "name": stock_name,
            "metadata": res['metadata'],
            "klines": clean_nan(res['data']),
            "logs": res['logs'],
            "data_source": raw_data.attrs.get("data_source", "remote") if hasattr(raw_data, "attrs") else "remote",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"数据获取失败: {e}")
