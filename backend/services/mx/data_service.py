from __future__ import annotations

from typing import Any

from backend.integrations.mx_data_adapter import run_query as adapter_run_query
from backend.services.mx.result import MXServiceResult


class DataService:
    tool_name = "mx-data"

    def run(self, query: str, timeout: int = 120) -> MXServiceResult:
        query = str(query or "").strip()
        if not query:
            return MXServiceResult(ok=False, tool=self.tool_name, query=query, error_message="query 不能为空")
        try:
            raw = adapter_run_query(query, timeout=timeout)
            parsed = self._parse(raw)
            warnings: list[str] = []
            if parsed.get("recognized_securities") and parsed.get("recognized_security_count", 0) <= 3 and len(query) > 80:
                warnings.append("识别到的证券数量偏少，可能存在多标的长查询解析不完整问题")
            return MXServiceResult(ok=True, tool=self.tool_name, query=query, raw=raw, parsed=parsed, warnings=warnings)
        except Exception as e:
            return MXServiceResult(ok=False, tool=self.tool_name, query=query, error_message=str(e))

    def _parse(self, raw: dict[str, Any]) -> dict[str, Any]:
        stdout = raw.get("stdout", "") or ""
        recognized: list[str] = []
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("- ") and " - A股" in line:
                recognized.append(line[2:])
        return {
            "recognized_securities": recognized,
            "recognized_security_count": len(recognized),
            "raw_json_present": raw.get("raw_json") is not None,
            "output_dir": raw.get("output_dir", ""),
        }
