from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


POSITIVE_TOKENS = ['同比增长', '增长', '回升', '改善', '向好', '订单增加', '扩产', '回购', '增持', '买入']
NEGATIVE_TOKENS = ['下滑', '亏损', '恶化', '疲软', '波动', '再融资', '问询', '警示']


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
        derived_from_preview = not any(search_result.get(key) for key in ['why_fell', 'decline_reason', 'summary', 'misjudgment_type', 'category', 'repair_logic', 'catalyst', 'bull_case', 'catalyst_clarity'])

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
            verdict = 'doubt' if (risk_points and derived_from_preview) else 'pass'
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
        direct = str(search.get('why_fell') or search.get('decline_reason') or search.get('summary') or '').strip()
        if direct:
            return direct
        preview_text = self._preview_text(search)
        if any(token in preview_text for token in ['下滑', '疲软', '波动', '承压', '再融资']):
            return '公告显示存在行业疲软、波动或再融资等压制因素'
        return ''

    def _misjudgment_type(self, search: dict[str, Any]) -> str:
        text = str(search.get('misjudgment_type') or search.get('category') or search.get('summary') or '').strip()
        if not text:
            text = self._preview_text(search)
        if '错杀' in text:
            return '错杀'
        if '行业' in text or '周期' in text or '疲软' in text:
            return '行业压制'
        if '恶化' in text or '亏损' in text or '下滑' in text:
            return '基本面恶化'
        return '不确定' if text else ''

    def _repair_logic(self, search: dict[str, Any]) -> str:
        direct = str(search.get('repair_logic') or search.get('catalyst') or search.get('bull_case') or '').strip()
        if direct:
            return direct
        preview_text = self._preview_text(search)
        if any(token in preview_text for token in POSITIVE_TOKENS):
            return '公告/资讯显示经营改善、订单或产能扩张等修复信号正在出现'
        return ''

    def _catalyst_clarity(self, search: dict[str, Any]) -> str:
        text = str(search.get('catalyst_clarity') or search.get('catalyst') or '').strip()
        if not text:
            text = self._preview_text(search)
        if not text:
            return ''
        if any(token in text for token in ['明确', '清晰', '落地', '验证', '同比增长', '订单增加', '回购', '增持', '买入']):
            return '清晰'
        return '不清晰'

    def _risk_points(self, search: dict[str, Any]) -> list[str]:
        value = search.get('risk_points')
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value not in (None, ''):
            text = str(value).strip()
            if text:
                return [part.strip() for part in text.replace('；', ',').split(',') if part.strip()]
        value = search.get('risks')
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value not in (None, ''):
            text = str(value).strip()
            if text:
                return [part.strip() for part in text.replace('；', ',').split(',') if part.strip()]
        preview_text = self._preview_text(search)
        return [token for token in NEGATIVE_TOKENS if token in preview_text]

    def _preview_text(self, search: dict[str, Any]) -> str:
        full_text = str(search.get('full_text') or '').strip()
        if full_text:
            return full_text
        preview = search.get('preview') or []
        if isinstance(preview, list):
            return ' '.join(str(item) for item in preview)
        return str(preview or '')
