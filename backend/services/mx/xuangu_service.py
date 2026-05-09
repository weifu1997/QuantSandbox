from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import re

import pandas as pd

from backend.core.data_center import DataCenter
from backend.integrations.mx_xuangu_adapter import run_query as adapter_run_query
from backend.services.mx.result import MXServiceResult


class XuanguService:
    tool_name = "mx-xuangu"

    def __init__(self) -> None:
        self.data_center = DataCenter()

    def run(self, query: str, timeout: int = 120) -> MXServiceResult:
        query = str(query or "").strip()
        if not query:
            return MXServiceResult(ok=False, tool=self.tool_name, query=query, error_message="query 不能为空")
        try:
            raw = adapter_run_query(query, timeout=timeout)
            parsed = self._parse(raw)
            return MXServiceResult(ok=True, tool=self.tool_name, query=query, raw=raw, parsed=parsed)
        except Exception as e:
            return MXServiceResult(ok=False, tool=self.tool_name, query=query, error_message=str(e))

    def _parse(self, raw: dict[str, Any]) -> dict[str, Any]:
        csv_path = raw.get("csv_path") or ""
        candidates: list[dict[str, Any]] = []
        hit_count = 0
        excluded = {"ST": None, "科创板": None, "创业板": None, "北交所": None}
        trade_date_hint = self._extract_trade_date_hint(raw)

        def first_non_empty(*values: Any) -> str:
            for value in values:
                if value is None:
                    continue
                text = str(value).strip()
                if text:
                    return text
            return ""

        enrichment_cache: dict[str, dict[str, str]] = {}

        if csv_path and Path(csv_path).exists():
            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            hit_count = len(rows)
            for row in rows:
                board = str(row.get("上市板块 截至2026.05.08最新", "") or row.get("上市板块", "")).strip()
                st_flag = str(row.get("ST股票", "")).strip()
                symbol = row.get("代码", "")
                latest_price = row.get("最新价(元) 2026.05.08", "") or row.get("最新价(元)", "")
                month_return = row.get("区间涨跌幅(%) 2026.04.08 - 2026.05.08", "")
                if not month_return:
                    month_return = self._compute_month_return(symbol=symbol, latest_price=latest_price)
                enrichment = enrichment_cache.get(symbol)
                if enrichment is None:
                    enrichment = self._fetch_candidate_enrichment(symbol, trade_date_hint=trade_date_hint)
                    enrichment_cache[symbol] = enrichment
                if not board:
                    board = enrichment.get('board', '')
                dividend_yield = row.get("年度股息率(%) 2025.12.31", "") or enrichment.get('dividend_yield', '')
                if st_flag:
                    excluded["ST"] = st_flag == "否"
                elif excluded["ST"] is None:
                    excluded["ST"] = True
                if board:
                    if "科创板" in board:
                        excluded["科创板"] = False
                    elif excluded["科创板"] is None:
                        excluded["科创板"] = True
                    if "创业板" in board:
                        excluded["创业板"] = False
                    elif excluded["创业板"] is None:
                        excluded["创业板"] = True
                    if "北交所" in board:
                        excluded["北交所"] = False
                    elif excluded["北交所"] is None:
                        excluded["北交所"] = True
                candidates.append(
                    {
                        "symbol": symbol,
                        "name": row.get("名称", ""),
                        "board": board,
                        "pe_ttm": row.get("市盈率(TTM)(倍) 2026.05.08", "") or row.get("市盈率(动)(倍) 2026.05.08", ""),
                        "pb": row.get("市净率(倍) 2026.05.08", ""),
                        "latest_price": latest_price,
                        "dividend_yield": dividend_yield,
                        "month_return": month_return,
                        "st_flag": st_flag if st_flag else "否",
                    }
                )

        if not candidates:
            raw_json = raw.get("raw_json") or {}
            data_list = (((raw_json.get("data") or {}).get("data") or {}).get("allResults") or {}).get("result", {}).get("dataList") or []
            hit_count = len(data_list)
            for row in data_list:
                symbol = first_non_empty(row.get("SECURITY_CODE"))
                latest_price = first_non_empty(row.get("NEWEST_PRICE"), row.get("LATEST_PRICE"))
                month_return = first_non_empty(row.get("MONTH_RETURN"))
                if not month_return:
                    month_return = self._compute_month_return(symbol=symbol, latest_price=latest_price)
                board = first_non_empty(row.get("MARKET_SHORT_NAME"))
                enrichment = enrichment_cache.get(symbol)
                if enrichment is None:
                    enrichment = self._fetch_candidate_enrichment(symbol, trade_date_hint=trade_date_hint)
                    enrichment_cache[symbol] = enrichment
                if not board:
                    board = enrichment.get('board', '')
                dividend_yield = first_non_empty(row.get("DIVIDEND_YIELD")) or enrichment.get('dividend_yield', '')
                st_flag = first_non_empty(row.get("ST股票"), row.get("ST_FLAG")) or '否'
                candidates.append(
                    {
                        "symbol": symbol,
                        "name": first_non_empty(row.get("SECURITY_SHORT_NAME")),
                        "board": board,
                        "pe_ttm": first_non_empty(row.get("010000_PE_D{2026-05-08}"), row.get("PE_TTM")),
                        "pb": first_non_empty(row.get("010000_PB<70>{2026-05-08}"), row.get("PB")),
                        "latest_price": latest_price,
                        "dividend_yield": dividend_yield,
                        "month_return": month_return,
                        "st_flag": st_flag,
                    }
                )

        for k, v in list(excluded.items()):
            if v is None:
                excluded[k] = "unknown"

        return {
            "hit_count": hit_count,
            "candidates": candidates,
            "excluded_checks": excluded,
            "csv_path": csv_path,
            "description_path": raw.get("description_path", ""),
        }

    def _compute_month_return(self, symbol: str, latest_price: str | float | int | None) -> str:
        current_price = self._safe_float(latest_price)
        if current_price is None or current_price <= 0:
            return ""
        try:
            end_date = self.data_center.get_latest_trade_date()
            start_dt = self._date_from_yyyymmdd(end_date) - timedelta(days=60)
            start_date = start_dt.strftime("%Y%m%d")
            df = self.data_center.fetch_stock_data(symbol, start_date=start_date, end_date=end_date)
            if df is None or df.empty or 'close' not in df.columns or 'date' not in df.columns:
                return ""
            working = df.copy()
            working['trade_day'] = pd.to_datetime(working['date'], errors='coerce').dt.strftime('%Y-%m-%d')
            working['close_num'] = pd.to_numeric(working['close'], errors='coerce')
            working = working.dropna(subset=['trade_day', 'close_num']).sort_values('date')
            working = working.drop_duplicates(subset=['trade_day'], keep='last').reset_index(drop=True)
            if len(working) < 21:
                return ""
            baseline = float(working['close_num'].iloc[-21])
            if baseline <= 0:
                return ""
            month_return = (current_price - baseline) / baseline * 100
            return f"{month_return:.2f}"
        except Exception:
            return ""

    @staticmethod
    def _date_from_yyyymmdd(value: str) -> datetime:
        return datetime.strptime(str(value), "%Y%m%d")

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(str(value).replace('%', '').replace('元', '').replace('倍', '').replace(',', '').strip())
        except Exception:
            return None

    def _fetch_candidate_enrichment(self, symbol: str, trade_date_hint: str = '') -> dict[str, str]:
        symbol = str(symbol or '').strip()
        if not symbol:
            return {'board': '', 'dividend_yield': ''}
        board = ''
        dividend_yield = ''
        try:
            meta = self.data_center._tushare_post(
                'stock_basic',
                {'ts_code': self.data_center._to_ts_code(symbol)},
                fields='ts_code,name,market,list_date',
            )
            items = ((meta.get('data') or {}).get('items') or [])
            if items and len(items[0]) >= 3 and items[0][2] is not None:
                board = str(items[0][2]).strip()
        except Exception:
            pass
        try:
            trade_date = trade_date_hint or self._latest_trade_date_from_price(symbol)
            basic = self.data_center._tushare_post(
                'daily_basic',
                {'ts_code': self.data_center._to_ts_code(symbol), 'trade_date': trade_date},
                fields='ts_code,trade_date,pb,pe,pe_ttm,dv_ratio,dv_ttm',
            )
            items = ((basic.get('data') or {}).get('items') or [])
            if items and len(items[0]) >= 7 and items[0][6] is not None:
                dividend_yield = str(items[0][6]).strip()
            elif items and len(items[0]) >= 6 and items[0][5] is not None:
                dividend_yield = str(items[0][5]).strip()
        except Exception:
            pass
        return {'board': board, 'dividend_yield': dividend_yield}

    def _extract_trade_date_hint(self, raw: dict[str, Any]) -> str:
        csv_path = raw.get('csv_path') or ''
        if csv_path and Path(csv_path).exists():
            try:
                with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames or []
                for name in fieldnames:
                    date = self._extract_yyyymmdd_from_text(name)
                    if date:
                        return date
            except Exception:
                pass
        raw_json = raw.get('raw_json') or {}
        columns = ((((raw_json.get('data') or {}).get('data') or {}).get('allResults') or {}).get('result', {}) or {}).get('columns') or []
        for col in columns:
            date = self._extract_yyyymmdd_from_text(str(col.get('dateMsg') or ''))
            if date:
                return date
            date = self._extract_yyyymmdd_from_text(str(col.get('title') or ''))
            if date:
                return date
        return ''

    @staticmethod
    def _extract_yyyymmdd_from_text(text: str) -> str:
        match = re.search(r'(20\d{2})[.\-/](\d{2})[.\-/](\d{2})', str(text or ''))
        if not match:
            return ''
        return ''.join(match.groups())

    def _latest_trade_date_from_price(self, symbol: str) -> str:
        end_date = self.data_center.get_latest_trade_date()
        df = self.data_center.fetch_stock_data(symbol, start_date=end_date, end_date=end_date)
        if df is not None and not df.empty and 'date' in df.columns:
            return pd.to_datetime(df['date']).max().strftime('%Y%m%d')
        return end_date
