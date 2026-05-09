from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LogicResult:
    verdict: str
    why_cheap: str
    why_fell: str
    misjudgment_type: str
    repair_logic: str
    catalyst_clarity: str
    risk_points: list[str] = field(default_factory=list)
    data_insufficient: bool = False


class LogicAnalyzer:
    """SOP1 Step 3 逻辑解释"""

    def analyze(self, candidate_data: dict[str, Any], search_result: dict[str, Any]) -> LogicResult:
        why_cheap = self._why_cheap(candidate_data)
        why_fell = self._why_fell(search_result)
        misjudgment_type = self._misjudgment_type(search_result)
        repair_logic = self._repair_logic(search_result)
        catalyst_clarity = self._catalyst_clarity(search_result)
        risk_points = self._risk_points(search_result)

        if not why_fell and not repair_logic:
            return LogicResult(
                verdict='insufficient',
                why_cheap=why_cheap,
                why_fell=why_fell,
                misjudgment_type=misjudgment_type or '不确定',
                repair_logic=repair_logic,
                catalyst_clarity=catalyst_clarity or '不确定',
                risk_points=risk_points,
                data_insufficient=True,
            )

        if misjudgment_type == '基本面恶化' and not repair_logic:
            verdict = 'eliminate'
        elif repair_logic and catalyst_clarity == '清晰':
            verdict = 'pass'
        elif repair_logic:
            verdict = 'doubt'
        else:
            verdict = 'doubt'

        return LogicResult(
            verdict=verdict,
            why_cheap=why_cheap,
            why_fell=why_fell,
            misjudgment_type=misjudgment_type or '不确定',
            repair_logic=repair_logic,
            catalyst_clarity=catalyst_clarity or '不确定',
            risk_points=risk_points,
            data_insufficient=False,
        )

    def _why_cheap(self, data: dict[str, Any]) -> str:
        reasons = []
        for key, label in [('pb', 'PB'), ('pe_ttm', 'PE'), ('dividend_yield', '股息率')]:
            value = data.get(key)
            if value not in (None, ''):
                reasons.append(f'{label}={value}')
        return '；'.join(reasons)

    def _why_fell(self, search: dict[str, Any]) -> str:
        return str(search.get('why_fell') or search.get('decline_reason') or search.get('summary') or '').strip()

    def _misjudgment_type(self, search: dict[str, Any]) -> str:
        text = str(search.get('misjudgment_type') or search.get('category') or search.get('summary') or '').strip()
        if '错杀' in text:
            return '错杀'
        if '行业' in text or '周期' in text:
            return '行业压制'
        if '恶化' in text or '亏损' in text or '下滑' in text:
            return '基本面恶化'
        return '不确定' if text else ''

    def _repair_logic(self, search: dict[str, Any]) -> str:
        return str(search.get('repair_logic') or search.get('catalyst') or search.get('bull_case') or '').strip()

    def _catalyst_clarity(self, search: dict[str, Any]) -> str:
        text = str(search.get('catalyst_clarity') or search.get('catalyst') or '').strip()
        if not text:
            return ''
        if any(token in text for token in ['明确', '清晰', '落地', '验证']):
            return '清晰'
        return '不清晰'

    def _risk_points(self, search: dict[str, Any]) -> list[str]:
        value = search.get('risk_points') or search.get('risks') or []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        if not text:
            return []
        return [part.strip() for part in text.replace('；', ',').split(',') if part.strip()]
