from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.workflows.low_value_flow.rules import safe_float


@dataclass
class StructureResult:
    passed: bool
    score: int
    near_support: bool | None
    volume_shrink: bool | None
    decline_slowing: bool | None
    consolidation: bool | None
    no_volume_breakdown: bool | None
    data_insufficient_fields: list[str] = field(default_factory=list)
    reject_reason: str | None = None


class StructureVerifier:
    """SOP1 Step 2 结构验证"""

    def verify(self, candidate_data: dict[str, Any]) -> StructureResult:
        near_support, support_missing = self._check_near_support(candidate_data)
        volume_shrink, volume_missing = self._check_volume_shrink(candidate_data)
        decline_slowing, decline_missing = self._check_decline_slowing(candidate_data)
        consolidation, consolidation_missing = self._check_consolidation(candidate_data)
        no_volume_breakdown, breakdown_missing = self._check_no_volume_breakdown(candidate_data)

        missing_fields = support_missing + volume_missing + decline_missing + consolidation_missing + breakdown_missing
        checks = [near_support, volume_shrink, decline_slowing, consolidation, no_volume_breakdown]
        score = sum(1 for item in checks if item is True)
        if score >= 2:
            return StructureResult(
                passed=True,
                score=score,
                near_support=near_support,
                volume_shrink=volume_shrink,
                decline_slowing=decline_slowing,
                consolidation=consolidation,
                no_volume_breakdown=no_volume_breakdown,
                data_insufficient_fields=missing_fields,
            )
        reason = '结构验证不足'
        if missing_fields and score == 0:
            reason = '数据不足: ' + ', '.join(missing_fields)
        return StructureResult(
            passed=False,
            score=score,
            near_support=near_support,
            volume_shrink=volume_shrink,
            decline_slowing=decline_slowing,
            consolidation=consolidation,
            no_volume_breakdown=no_volume_breakdown,
            data_insufficient_fields=missing_fields,
            reject_reason=reason,
        )

    def _check_near_support(self, data: dict[str, Any]) -> tuple[bool | None, list[str]]:
        latest_price = safe_float(data.get('latest_price'))
        support_price = safe_float(data.get('support_price') or data.get('prior_low_price'))
        if latest_price is None or support_price is None or support_price <= 0:
            return None, ['latest_price', 'support_price']
        gap = abs(latest_price - support_price) / support_price
        return gap <= 0.05, []

    def _check_volume_shrink(self, data: dict[str, Any]) -> tuple[bool | None, list[str]]:
        turnover_short = safe_float(data.get('turnover_10_15d'))
        turnover_3m = safe_float(data.get('turnover_3m'))
        if turnover_short is None or turnover_3m is None:
            return None, ['turnover_10_15d', 'turnover_3m']
        return turnover_short < turnover_3m, []

    def _check_decline_slowing(self, data: dict[str, Any]) -> tuple[bool | None, list[str]]:
        recent = safe_float(data.get('decline_slope_10d'))
        previous = safe_float(data.get('decline_slope_30d'))
        if recent is None or previous is None:
            return None, ['decline_slope_10d', 'decline_slope_30d']
        return abs(recent) < abs(previous), []

    def _check_consolidation(self, data: dict[str, Any]) -> tuple[bool | None, list[str]]:
        range_pct = safe_float(data.get('consolidation_range_pct'))
        days = safe_float(data.get('consolidation_days'))
        if range_pct is None or days is None:
            return None, ['consolidation_range_pct', 'consolidation_days']
        return range_pct <= 8 and days >= 10, []

    def _check_no_volume_breakdown(self, data: dict[str, Any]) -> tuple[bool | None, list[str]]:
        breakdown_days = safe_float(data.get('volume_breakdown_days'))
        if breakdown_days is None:
            return None, ['volume_breakdown_days']
        return breakdown_days <= 0, []
