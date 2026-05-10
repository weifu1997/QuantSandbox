from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.models.watchlist import LeftSideGrade
from backend.workflows.low_value_flow.rules import safe_float


@dataclass
class LeftSideGradeResult:
    grade: str
    score: int
    volume_confirmed: bool
    support_valid: bool
    anchor_reliable: bool
    catalyst_ready: bool
    valuation_safe: bool


class LeftSideGrader:
    def grade(self, data: dict[str, Any]) -> LeftSideGradeResult:
        checks = {
            'volume_confirmed': self._volume_confirmed(data),
            'support_valid': self._support_valid(data),
            'anchor_reliable': self._anchor_reliable(data),
            'catalyst_ready': self._catalyst_ready(data),
            'valuation_safe': self._valuation_safe(data),
        }
        score = sum(1 for value in checks.values() if value)
        if score >= 4:
            grade = LeftSideGrade.A.value
        elif score >= 2:
            grade = LeftSideGrade.B.value
        else:
            grade = LeftSideGrade.C.value
        return LeftSideGradeResult(grade=grade, score=score, **checks)

    def _volume_confirmed(self, data: dict[str, Any]) -> bool:
        avg10 = safe_float(data.get('avg_volume_10d') or data.get('volume_avg_10d') or data.get('turnover_10d'))
        avg20 = safe_float(data.get('avg_volume_20d') or data.get('volume_avg_20d') or data.get('turnover_20d'))
        if avg10 is None or avg20 is None or avg20 <= 0:
            return False
        return avg10 < avg20 * 0.6

    def _support_valid(self, data: dict[str, Any]) -> bool:
        latest = safe_float(data.get('latest_price'))
        prior_low = safe_float(data.get('prior_low_price') or data.get('support_price'))
        days = safe_float(data.get('prior_low_days_ago') or data.get('support_age_days'))
        if latest is None or prior_low is None or prior_low <= 0 or days is None:
            return False
        return abs(latest - prior_low) / prior_low <= 0.05 and days >= 20

    def _anchor_reliable(self, data: dict[str, Any]) -> bool:
        ma60_gap = safe_float(data.get('ma60_gap_pct'))
        if ma60_gap is None:
            ma60 = safe_float(data.get('ma60'))
            latest = safe_float(data.get('latest_price'))
            if ma60 is None or latest is None or latest <= 0:
                return False
            ma60_gap = abs(ma60 - latest) / latest * 100
        return ma60_gap <= 15

    def _catalyst_ready(self, data: dict[str, Any]) -> bool:
        catalyst = str(data.get('catalyst_signal') or data.get('repair_logic') or data.get('recent_catalyst') or '').strip()
        return bool(catalyst)

    def _valuation_safe(self, data: dict[str, Any]) -> bool:
        pe = safe_float(data.get('pe_ttm'))
        pb = safe_float(data.get('pb'))
        return (pe is not None and pe < 15) or (pb is not None and pb < 1.0)
