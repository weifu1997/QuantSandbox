from __future__ import annotations

from dataclasses import dataclass
from typing import Any


LOSS_RISK_THRESHOLD = 0.0
MISSING_DATA_PREFIX = "数据不足:"
OTHER_MAJOR_RISK_FLAGS = {
    "重大风险",
    "重大诉讼",
    "退市风险",
    "债务违约",
    "流动性危机",
    "财务造假",
    "信披异常",
}


@dataclass
class QuickRiskResult:
    reject: bool
    reason: str | None
    data_insufficient: bool = False


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(str(value).replace('%', '').replace('元', '').replace('倍', '').replace(',', '').strip())
    except Exception:
        return None


def _data_insufficient(message: str) -> QuickRiskResult:
    return QuickRiskResult(reject=False, reason=f"{MISSING_DATA_PREFIX} {message}", data_insufficient=True)


def _normalize_flag_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        return [part.strip() for part in text.replace('；', ',').replace('、', ',').split(',') if part.strip()]
    return [str(value).strip()]


def _check_revenue_cliff(data: dict[str, Any]) -> QuickRiskResult:
    latest = safe_float(data.get('revenue_yoy'))
    previous = safe_float(data.get('revenue_growth'))
    if latest is None or previous is None:
        return _data_insufficient('营收字段缺失')
    if latest <= -20 and previous <= -20:
        return QuickRiskResult(reject=True, reason='营收断崖')
    return QuickRiskResult(reject=False, reason=None)


def _check_loss_expanding(data: dict[str, Any]) -> QuickRiskResult:
    latest = safe_float(data.get('profit_yoy'))
    previous = safe_float(data.get('net_profit_change'))
    if latest is None or previous is None:
        return _data_insufficient('净利润字段缺失')
    if latest < 0 and previous < 0 and latest < previous:
        return QuickRiskResult(reject=True, reason='亏损快速扩大')
    return QuickRiskResult(reject=False, reason=None)


def _check_liquidity_crisis(data: dict[str, Any]) -> QuickRiskResult:
    current_ratio = safe_float(data.get('current_ratio'))
    quick_ratio = safe_float(data.get('quick_ratio'))
    if current_ratio is None or quick_ratio is None:
        return _data_insufficient('流动性字段缺失')
    if current_ratio < 1.0 or quick_ratio < 0.7:
        return QuickRiskResult(reject=True, reason='流动性危机')
    return QuickRiskResult(reject=False, reason=None)


def _check_financial_anomaly(data: dict[str, Any]) -> QuickRiskResult:
    audit = str(data.get('audit_opinion', '') or '').strip()
    inquiry = str(data.get('regulatory_inquiry', '') or '').strip()
    if not audit and not inquiry:
        return _data_insufficient('财务/监管字段缺失')
    bad_audit = any(token in audit for token in ['保留', '否定', '无法表示'])
    bad_inquiry = any(token in inquiry for token in ['问询', '立案', '处罚', '异常'])
    if bad_audit or bad_inquiry:
        return QuickRiskResult(reject=True, reason='财务/信披异常')
    return QuickRiskResult(reject=False, reason=None)


def _check_other_risks(data: dict[str, Any]) -> QuickRiskResult:
    flags = _normalize_flag_list(data.get('risk_flags'))
    if not flags:
        return _data_insufficient('风险标记缺失')
    if any(any(keyword in flag for keyword in OTHER_MAJOR_RISK_FLAGS) for flag in flags):
        return QuickRiskResult(reject=True, reason='其他重大风险')
    return QuickRiskResult(reject=False, reason=None)


def should_reject_in_quick_risk(candidate: dict[str, Any]) -> tuple[bool, str | None]:
    result = quick_risk_decision(candidate)
    return result.reject, result.reason


def quick_risk_decision(candidate: dict[str, Any]) -> QuickRiskResult:
    st_flag = str(candidate.get('st_flag', '')).strip()
    if st_flag in {'是', 'true', 'True'}:
        return QuickRiskResult(reject=True, reason='退市/ST风险')

    pe = safe_float(candidate.get('pe_ttm'))
    if pe is not None and pe < LOSS_RISK_THRESHOLD:
        return QuickRiskResult(reject=True, reason='亏损扩大')

    checks = [
        _check_revenue_cliff(candidate),
        _check_loss_expanding(candidate),
        _check_liquidity_crisis(candidate),
        _check_financial_anomaly(candidate),
        _check_other_risks(candidate),
    ]
    insufficient_reasons: list[str] = []
    complete_checks = 0
    for result in checks:
        if result.reject:
            return result
        if result.data_insufficient and result.reason:
            insufficient_reasons.append(result.reason.replace(f'{MISSING_DATA_PREFIX} ', ''))
        else:
            complete_checks += 1
    if complete_checks == 0 and insufficient_reasons:
        merged = '；'.join(dict.fromkeys(insufficient_reasons))
        return QuickRiskResult(reject=False, reason=f'{MISSING_DATA_PREFIX} {merged}', data_insufficient=True)
    return QuickRiskResult(reject=False, reason=None)
