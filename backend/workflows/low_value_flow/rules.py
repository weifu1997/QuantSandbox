from __future__ import annotations

from typing import Any


LOSS_RISK_THRESHOLD = 0.0


def should_reject_in_quick_risk(candidate: dict[str, Any]) -> tuple[bool, str | None]:
    st_flag = str(candidate.get("st_flag", "")).strip()
    if st_flag in {"是", "true", "True"}:
        return True, "退市/ST风险"

    pe_raw = candidate.get("pe_ttm", "")
    try:
        pe = float(pe_raw)
        if pe < LOSS_RISK_THRESHOLD:
            return True, "亏损扩大"
    except Exception:
        pass

    return False, None


def structure_decision_from_data(data_result: dict[str, Any]) -> tuple[str, list[str]]:
    recognized_count = int(data_result.get("recognized_security_count", 0) or 0)
    warnings: list[str] = []
    if recognized_count == 0:
        return "insufficient", ["未识别到证券"]
    if data_result.get("warnings"):
        warnings.extend(data_result["warnings"])
    return ("partial" if warnings else "ok"), warnings
