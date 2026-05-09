from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from backend.integrations.mx_xuangu_adapter import run_query as adapter_run_query
from backend.services.mx.result import MXServiceResult


class XuanguService:
    tool_name = "mx-xuangu"

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

        if csv_path and Path(csv_path).exists():
            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            hit_count = len(rows)
            for row in rows:
                board = str(row.get("上市板块 截至2026.05.08最新", "") or row.get("上市板块", "")).strip()
                st_flag = str(row.get("ST股票", "")).strip()
                if st_flag:
                    excluded["ST"] = st_flag == "否"
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
                        "symbol": row.get("代码", ""),
                        "name": row.get("名称", ""),
                        "board": board,
                        "pe_ttm": row.get("市盈率(TTM)(倍) 2026.05.08", ""),
                        "pb": row.get("市净率(倍) 2026.05.08", ""),
                        "dividend_yield": row.get("年度股息率(%) 2025.12.31", ""),
                        "month_return": row.get("区间涨跌幅(%) 2026.04.08 - 2026.05.08", ""),
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
