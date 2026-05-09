from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from backend.integrations.mx_zixuan_adapter import run_query as zixuan_adapter_run_query
from backend.integrations.mx_moni_adapter import run_query as moni_adapter_run_query
from backend.services.mx.result import MXServiceResult


class ZixuanService:
    tool_name = "mx-zixuan"

    def run(self, query: str, timeout: int = 120) -> MXServiceResult:
        query = str(query or "").strip()
        if not query:
            return MXServiceResult(ok=False, tool=self.tool_name, query=query, error_message="query 不能为空")
        try:
            raw = zixuan_adapter_run_query(query, timeout=timeout)
            parsed = self._parse(raw)
            return MXServiceResult(ok=True, tool=self.tool_name, query=query, raw=raw, parsed=parsed)
        except Exception as e:
            return MXServiceResult(ok=False, tool=self.tool_name, query=query, error_message=str(e))

    def _parse(self, raw: dict[str, Any]) -> dict[str, Any]:
        stdout = raw.get("stdout", "") or ""
        csv_path = raw.get("csv_path", "") or ""
        holdings: list[dict[str, Any]] = []
        if csv_path and Path(csv_path).exists():
            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    holdings.append(row)
        return {
            "line_count": len([line for line in stdout.splitlines() if line.strip()]),
            "stdout_preview": [line.strip() for line in stdout.splitlines() if line.strip()][:20],
            "raw_json_present": raw.get("raw_json") is not None,
            "csv_path": csv_path,
            "holdings_count": len(holdings),
            "holdings": holdings,
        }


class MoniService:
    tool_name = "mx-moni"

    def run(self, query: str, timeout: int = 120) -> MXServiceResult:
        query = str(query or "").strip()
        if not query:
            return MXServiceResult(ok=False, tool=self.tool_name, query=query, error_message="query 不能为空")
        try:
            raw = moni_adapter_run_query(query, timeout=timeout)
            parsed = self._parse(raw)
            return MXServiceResult(ok=True, tool=self.tool_name, query=query, raw=raw, parsed=parsed)
        except Exception as e:
            return MXServiceResult(ok=False, tool=self.tool_name, query=query, error_message=str(e))

    def _parse(self, raw: dict[str, Any]) -> dict[str, Any]:
        stdout = raw.get("stdout", "") or ""
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        return {
            "line_count": len(lines),
            "preview": lines[:20],
            "raw_json_present": raw.get("raw_json") is not None,
            "txt_path": raw.get("txt_path", ""),
            "json_path": raw.get("json_path", ""),
        }
