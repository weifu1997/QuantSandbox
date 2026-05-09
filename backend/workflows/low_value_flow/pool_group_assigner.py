from __future__ import annotations

from typing import Any

from backend.models.watchlist import PoolGroup
from backend.workflows.low_value_flow.logic_analyzer import LogicResult
from backend.workflows.low_value_flow.rules import safe_float


class PoolGroupAssigner:
    """SOP1 Step 4 观察池分组"""

    def assign(self, candidate_data: dict[str, Any], logic_result: LogicResult) -> PoolGroup:
        if self._is_high_dividend(candidate_data):
            return PoolGroup.HIGH_DIVIDEND
        if self._is_depth_value(candidate_data, logic_result):
            return PoolGroup.DEPTH_VALUE
        if self._is_cycle_reversal(candidate_data, logic_result):
            return PoolGroup.CYCLE_REVERSAL
        return PoolGroup.OBSCURE

    def _is_depth_value(self, data: dict[str, Any], logic: LogicResult) -> bool:
        pb = safe_float(data.get('pb'))
        pe = safe_float(data.get('pe_ttm'))
        div = safe_float(data.get('dividend_yield'))
        return (pb is not None and pb <= 1.0) and (pe is not None and pe <= 15) and (div is not None and div >= 2.0) and logic.verdict in {'pass', 'doubt'}

    def _is_cycle_reversal(self, data: dict[str, Any], logic: LogicResult) -> bool:
        board = str(data.get('board') or '')
        return any(token in board for token in ['周期', '资源', '化工', '有色']) or logic.misjudgment_type == '行业压制'

    def _is_high_dividend(self, data: dict[str, Any]) -> bool:
        div = safe_float(data.get('dividend_yield'))
        return div is not None and div > 3

    def _is_obscure(self, data: dict[str, Any], logic: LogicResult) -> bool:
        return logic.catalyst_clarity == '清晰'
