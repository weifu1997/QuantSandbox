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

    def run_raw(self, query: str, timeout: int = 120) -> dict[str, Any]:
        query = str(query or "").strip()
        if not query:
            raise RuntimeError("query 不能为空")
        return adapter_run_query(query, timeout=timeout)

    def parse_core(self, raw: dict[str, Any]) -> dict[str, Any]:
        return self._parse(raw, enrich=False)

    def enrich_candidates(self, parsed: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
        return self._parse(raw, enrich=True, pre_parsed=parsed)

    def run(self, query: str, timeout: int = 120) -> MXServiceResult:
        query = str(query or "").strip()
        if not query:
            return MXServiceResult(ok=False, tool=self.tool_name, query=query, error_message="query 不能为空")
        try:
            raw = self.run_raw(query, timeout=timeout)
            parsed = self._parse(raw, enrich=True)
            return MXServiceResult(ok=True, tool=self.tool_name, query=query, raw=raw, parsed=parsed)
        except Exception as e:
            return MXServiceResult(ok=False, tool=self.tool_name, query=query, error_message=str(e))

    def _parse(self, raw: dict[str, Any], enrich: bool = True, pre_parsed: dict[str, Any] | None = None) -> dict[str, Any]:
        csv_path = raw.get("csv_path") or ""
        if pre_parsed:
            candidates: list[dict[str, Any]] = list(pre_parsed.get("candidates", []) or [])
            hit_count = int(pre_parsed.get("hit_count", 0) or 0)
            excluded = dict(pre_parsed.get("excluded_checks", {}) or {"ST": None, "科创板": None, "创业板": None, "北交所": None})
        else:
            candidates = []
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

        def value_from_row(row: dict[str, Any], *, regex_patterns: list[str], plain_names: list[str] | None = None, hardcoded_names: list[str] | None = None) -> str:
            return self._find_column_value(
                row,
                regex_patterns=regex_patterns,
                plain_names=plain_names or [],
                hardcoded_names=hardcoded_names or [],
            )

        enrichment_cache: dict[str, dict[str, Any]] = {}

        if not pre_parsed and csv_path and Path(csv_path).exists():
            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            hit_count = len(rows)
            for row in rows:
                board = value_from_row(
                    row,
                    regex_patterns=[r'^上市板块\s+截至\d{4}\.\d{2}\.\d{2}最新$', r'^上市板块'],
                    plain_names=['上市板块'],
                    hardcoded_names=['上市板块 截至2026.05.08最新'],
                )
                st_flag = str(row.get("ST股票", "")).strip()
                symbol = row.get("代码", "")
                latest_price = value_from_row(
                    row,
                    regex_patterns=[r'^最新价\(元\)\s+\d{4}\.\d{2}\.\d{2}$'],
                    plain_names=['最新价(元)'],
                    hardcoded_names=['最新价(元) 2026.05.08'],
                )
                month_return = value_from_row(
                    row,
                    regex_patterns=[r'^区间涨跌幅\(%\)\s+\d{4}\.\d{2}\.\d{2}\s+-\s+\d{4}\.\d{2}\.\d{2}$'],
                    plain_names=['区间涨跌幅(%)'],
                    hardcoded_names=['区间涨跌幅(%) 2026.04.08 - 2026.05.08'],
                )
                if enrich and not month_return:
                    month_return = self._compute_month_return(symbol=symbol, latest_price=latest_price)
                enrichment = {}
                if enrich:
                    enrichment = enrichment_cache.get(symbol)
                    if enrichment is None:
                        enrichment = self._fetch_candidate_enrichment(symbol, trade_date_hint=trade_date_hint)
                        enrichment_cache[symbol] = enrichment
                    if not board:
                        board = enrichment.get('board', '')
                dividend_yield = value_from_row(
                    row,
                    regex_patterns=[r'^年度股息率\(%\)\s+\d{4}\.\d{2}\.\d{2}$'],
                    plain_names=['年度股息率(%)'],
                    hardcoded_names=['年度股息率(%) 2025.12.31'],
                ) or (enrichment.get('dividend_yield', '') if enrich else '')
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
                        "pe_ttm": value_from_row(
                            row,
                            regex_patterns=[r'^市盈率\(TTM\)\(倍\)\s+\d{4}\.\d{2}\.\d{2}$', r'^市盈率\(动\)\(倍\)\s+\d{4}\.\d{2}\.\d{2}$'],
                            plain_names=['市盈率(TTM)(倍)', '市盈率(动)(倍)'],
                            hardcoded_names=['市盈率(TTM)(倍) 2026.05.08', '市盈率(动)(倍) 2026.05.08'],
                        ),
                        "pb": value_from_row(
                            row,
                            regex_patterns=[r'^市净率\(倍\)\s+\d{4}\.\d{2}\.\d{2}$'],
                            plain_names=['市净率(倍)'],
                            hardcoded_names=['市净率(倍) 2026.05.08'],
                        ),
                        "latest_price": latest_price,
                        "dividend_yield": dividend_yield,
                        "month_return": month_return,
                        "st_flag": st_flag if st_flag else "否",
                        "revenue_yoy": enrichment.get('revenue_yoy', ''),
                        "revenue_growth": enrichment.get('revenue_growth', ''),
                        "profit_yoy": enrichment.get('profit_yoy', ''),
                        "net_profit_change": enrichment.get('net_profit_change', ''),
                        "current_ratio": enrichment.get('current_ratio', ''),
                        "quick_ratio": enrichment.get('quick_ratio', ''),
                        "audit_opinion": enrichment.get('audit_opinion', ''),
                        "regulatory_inquiry": enrichment.get('regulatory_inquiry', ''),
                        "risk_flags": enrichment.get('risk_flags', []),
                    }
                )

        if not pre_parsed and not candidates:
            raw_json = raw.get("raw_json") or {}
            data_list = (((raw_json.get("data") or {}).get("data") or {}).get("allResults") or {}).get("result", {}).get("dataList") or []
            hit_count = len(data_list)
            for row in data_list:
                symbol = first_non_empty(row.get("SECURITY_CODE"))
                latest_price = first_non_empty(row.get("NEWEST_PRICE"), row.get("LATEST_PRICE"))
                month_return = first_non_empty(row.get("MONTH_RETURN"))
                if enrich and not month_return:
                    month_return = self._compute_month_return(symbol=symbol, latest_price=latest_price)
                board = first_non_empty(row.get("MARKET_SHORT_NAME"))
                enrichment = {}
                if enrich:
                    enrichment = enrichment_cache.get(symbol)
                    if enrichment is None:
                        enrichment = self._fetch_candidate_enrichment(symbol, trade_date_hint=trade_date_hint)
                        enrichment_cache[symbol] = enrichment
                    if not board:
                        board = enrichment.get('board', '')
                dividend_yield = first_non_empty(row.get("DIVIDEND_YIELD")) or (enrichment.get('dividend_yield', '') if enrich else '')
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
                        "revenue_yoy": enrichment.get('revenue_yoy', ''),
                        "revenue_growth": enrichment.get('revenue_growth', ''),
                        "profit_yoy": enrichment.get('profit_yoy', ''),
                        "net_profit_change": enrichment.get('net_profit_change', ''),
                        "current_ratio": enrichment.get('current_ratio', ''),
                        "quick_ratio": enrichment.get('quick_ratio', ''),
                        "audit_opinion": enrichment.get('audit_opinion', ''),
                        "regulatory_inquiry": enrichment.get('regulatory_inquiry', ''),
                        "risk_flags": enrichment.get('risk_flags', []),
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

    def _fetch_candidate_enrichment(self, symbol: str, trade_date_hint: str = '') -> dict[str, Any]:
        symbol = str(symbol or '').strip()
        if not symbol:
            return {
                'board': '',
                'dividend_yield': '',
                'revenue_yoy': '',
                'revenue_growth': '',
                'profit_yoy': '',
                'net_profit_change': '',
                'current_ratio': '',
                'quick_ratio': '',
                'audit_opinion': '',
                'regulatory_inquiry': '',
                'risk_flags': [],
            }
        enrichment: dict[str, Any] = {
            'board': '',
            'dividend_yield': '',
            'revenue_yoy': '',
            'revenue_growth': '',
            'profit_yoy': '',
            'net_profit_change': '',
            'current_ratio': '',
            'quick_ratio': '',
            'audit_opinion': '',
            'regulatory_inquiry': '',
            'risk_flags': [],
        }
        try:
            meta = self.data_center._tushare_post(
                'stock_basic',
                {'ts_code': self.data_center._to_ts_code(symbol)},
                fields='ts_code,name,market,list_date',
            )
            items = ((meta.get('data') or {}).get('items') or [])
            if items and len(items[0]) >= 3 and items[0][2] is not None:
                enrichment['board'] = str(items[0][2]).strip()
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
                enrichment['dividend_yield'] = str(items[0][6]).strip()
            elif items and len(items[0]) >= 6 and items[0][5] is not None:
                enrichment['dividend_yield'] = str(items[0][5]).strip()
        except Exception:
            pass
        try:
            fina = self.data_center._tushare_post(
                'fina_indicator',
                {'ts_code': self.data_center._to_ts_code(symbol), 'limit': 2},
                fields='ts_code,end_date,q_sales_yoy,sales_yoy,q_dtprofit_yoy,dt_netprofit_yoy,current_ratio,quick_ratio,audit_result',
            )
            table = fina.get('data') or {}
            fields = table.get('fields') or []
            items = table.get('items') or []
            if fields and items:
                latest = {fields[i]: items[0][i] for i in range(min(len(fields), len(items[0])))}
                previous = {fields[i]: items[1][i] for i in range(min(len(fields), len(items[1])))} if len(items) > 1 else latest
                enrichment['revenue_yoy'] = self._clean_metric_value(latest.get('q_sales_yoy') or latest.get('sales_yoy'))
                enrichment['revenue_growth'] = self._clean_metric_value(previous.get('q_sales_yoy') or previous.get('sales_yoy'))
                enrichment['profit_yoy'] = self._clean_metric_value(latest.get('q_dtprofit_yoy') or latest.get('dt_netprofit_yoy'))
                enrichment['net_profit_change'] = self._clean_metric_value(previous.get('q_dtprofit_yoy') or previous.get('dt_netprofit_yoy'))
                enrichment['current_ratio'] = self._clean_metric_value(latest.get('current_ratio'))
                enrichment['quick_ratio'] = self._clean_metric_value(latest.get('quick_ratio'))
                enrichment['audit_opinion'] = self._clean_metric_value(latest.get('audit_result'))
        except Exception:
            pass
        if enrichment['audit_opinion']:
            flags: list[str] = []
            audit = str(enrichment['audit_opinion'])
            if any(token in audit for token in ['保留', '否定', '无法表示']):
                flags.append('审计意见异常')
            enrichment['risk_flags'] = flags
        return enrichment

    @staticmethod
    def _clean_metric_value(value: Any) -> str:
        if value is None:
            return ''
        text = str(value).strip()
        if not text or text.lower() == 'nan':
            return ''
        return text

    @staticmethod
    def _match_dynamic_column(fieldnames: list[str], regex_patterns: list[str]) -> str:
        for pattern in regex_patterns:
            regex = re.compile(pattern)
            for name in fieldnames:
                if regex.match(str(name or '').strip()):
                    return name
        return ''

    @staticmethod
    def _match_plain_column(fieldnames: list[str], plain_names: list[str]) -> str:
        normalized = {str(name or '').strip(): name for name in fieldnames}
        for plain_name in plain_names:
            if plain_name in normalized:
                return normalized[plain_name]
        return ''

    def _find_column_value(
        self,
        row: dict[str, Any],
        *,
        regex_patterns: list[str],
        plain_names: list[str],
        hardcoded_names: list[str],
    ) -> str:
        fieldnames = list(row.keys())
        dynamic_name = self._match_dynamic_column(fieldnames, regex_patterns)
        if dynamic_name:
            value = row.get(dynamic_name)
            if value is not None and str(value).strip():
                return str(value).strip()

        plain_name = self._match_plain_column(fieldnames, plain_names)
        if plain_name:
            value = row.get(plain_name)
            if value is not None and str(value).strip():
                return str(value).strip()

        for hardcoded_name in hardcoded_names:
            value = row.get(hardcoded_name)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ''

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
