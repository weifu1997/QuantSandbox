from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BottomSearchParseResult:
    catalyst_summary: str
    catalyst_clarity: str
    right_side_signal: bool
    why_now: str
    risk_points: list[str] = field(default_factory=list)


class BottomSearchParser:
    def parse(self, text: str) -> BottomSearchParseResult:
        clean = str(text or '').strip()
        catalyst_clarity = self._catalyst_clarity(clean)
        right_side_signal = self._right_side_signal(clean)
        catalyst_summary = self._catalyst_summary(clean)
        why_now = self._why_now(clean)
        risk_points = self._risk_points(clean)
        return BottomSearchParseResult(
            catalyst_summary=catalyst_summary,
            catalyst_clarity=catalyst_clarity,
            right_side_signal=right_side_signal,
            why_now=why_now,
            risk_points=risk_points,
        )

    @staticmethod
    def _catalyst_clarity(text: str) -> str:
        if any(token in text for token in ['同比增长', '业绩说明会', '一季报', '年报', '订单增加', '扩产', '买入评级']):
            return 'clear'
        if any(token in text for token in ['预期', '有望', '可能', '关注']):
            return 'emerging'
        return 'unclear'

    @staticmethod
    def _right_side_signal(text: str) -> bool:
        return any(token in text for token in ['同比增长', '改善', '修复', '向好', '订单增加', '评级: 买入', '业绩实现增长'])

    @staticmethod
    def _catalyst_summary(text: str) -> str:
        for token in ['订单增加', '同比增长', '扩产', '修复', '业绩实现增长', '评级: 买入']:
            if token in text:
                return token
        return text[:120]

    @staticmethod
    def _why_now(text: str) -> str:
        for token in ['同比增长', '改善', '修复', '向好', '扩产', '订单增加']:
            if token in text:
                return token
        return ''

    @staticmethod
    def _risk_points(text: str) -> list[str]:
        hits = []
        for token in ['疲软', '下滑', '波动', '再融资', '减持', '风险提示']:
            if token in text:
                hits.append(token)
        return hits
