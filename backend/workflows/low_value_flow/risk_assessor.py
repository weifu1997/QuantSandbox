from __future__ import annotations

from typing import Any

from backend.models import RiskLevel


class RiskAssessor:
    @staticmethod
    def safe_float(value: object) -> float | None:
        try:
            if value is None or value == "":
                return None
            s = str(value).replace('%', '').replace('元', '').replace('倍', '').replace(',', '').strip()
            return float(s)
        except Exception:
            return None

    def derive_risk_level(self, candidate_data: dict | None) -> RiskLevel:
        data = candidate_data or {}
        pb = self.safe_float(data.get('pb'))
        pe = self.safe_float(data.get('pe_ttm'))
        div = self.safe_float(data.get('dividend_yield'))
        month_ret = self.safe_float(data.get('month_return'))

        score = 0
        if pb is not None:
            if pb <= 1.0:
                score += 1
            elif pb >= 1.4:
                score -= 1
        if pe is not None:
            if 0 < pe <= 15:
                score += 1
            elif pe >= 18:
                score -= 1
        if div is not None:
            if div >= 3:
                score += 1
            elif div < 2:
                score -= 1
        if month_ret is not None:
            if -15 <= month_ret <= -5:
                score += 1
            elif month_ret < -20:
                score -= 2

        if score >= 2:
            return RiskLevel.LOW
        if score <= -1:
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM
