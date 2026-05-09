from __future__ import annotations

from typing import Any

from backend.integrations.mx_search_adapter import run_query as adapter_run_query
from backend.services.mx.result import MXServiceResult


class SearchService:
    tool_name = "mx-search"

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
        stdout = raw.get("stdout", "") or ""
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        return {
            "line_count": len(lines),
            "preview": lines[:20],
            "raw_json_present": raw.get("raw_json") is not None,
            "txt_path": raw.get("txt_path", ""),
        }
