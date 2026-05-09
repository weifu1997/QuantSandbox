from __future__ import annotations

from backend.models.watchlist import PoolGroup
from backend.workflows.low_value_flow.logic_analyzer import LogicAnalyzer
from backend.workflows.low_value_flow.pool_group_assigner import PoolGroupAssigner
from backend.workflows.low_value_flow.rules import quick_risk_decision
from backend.workflows.low_value_flow.structure_verifier import StructureVerifier


class TestQuickRiskEnhanced:
    def test_rejects_revenue_cliff(self):
        result = quick_risk_decision({
            'st_flag': '否',
            'pe_ttm': '10',
            'revenue_yoy': '-30',
            'revenue_growth': '-25',
            'profit_yoy': '5',
            'net_profit_change': '3',
            'current_ratio': '1.5',
            'quick_ratio': '1.1',
            'audit_opinion': '标准无保留',
            'regulatory_inquiry': '无',
            'risk_flags': ['正常'],
        })
        assert result.reject is True
        assert result.reason == '营收断崖'

    def test_marks_missing_data_as_insufficient(self):
        result = quick_risk_decision({'st_flag': '否', 'pe_ttm': '10'})
        assert result.reject is False
        assert result.data_insufficient is True
        assert result.reason.startswith('数据不足:')


class TestStructureVerifier:
    def test_passes_with_two_positive_signals(self):
        verifier = StructureVerifier()
        result = verifier.verify({
            'latest_price': '10',
            'support_price': '9.7',
            'turnover_10_15d': '1.2',
            'turnover_3m': '2.1',
            'decline_slope_10d': '-0.8',
            'decline_slope_30d': '-1.5',
            'consolidation_range_pct': '7',
            'consolidation_days': '12',
            'volume_breakdown_days': '0',
        })
        assert result.passed is True
        assert result.score >= 2
        assert result.volume_shrink is True

    def test_insufficient_when_core_fields_missing(self):
        verifier = StructureVerifier()
        result = verifier.verify({'latest_price': '10'})
        assert result.passed is False
        assert result.data_insufficient_fields
        assert result.reject_reason.startswith('数据不足:')


class TestLogicAnalyzer:
    def test_pass_when_repair_logic_and_clear_catalyst(self):
        analyzer = LogicAnalyzer()
        result = analyzer.analyze(
            {'pb': '0.8', 'pe_ttm': '9.5', 'dividend_yield': '4.2'},
            {
                'why_fell': '行业景气回落导致股价承压',
                'misjudgment_type': '行业压制',
                'repair_logic': '行业库存去化，盈利修复预期提升',
                'catalyst_clarity': '明确催化即将验证',
                'risk_points': ['景气反复'],
            },
        )
        assert result.verdict == 'pass'
        assert result.misjudgment_type == '行业压制'
        assert result.catalyst_clarity == '清晰'

    def test_eliminate_when_fundamental_deteriorates_without_repair(self):
        analyzer = LogicAnalyzer()
        result = analyzer.analyze(
            {'pb': '1.2'},
            {
                'why_fell': '利润恶化且现金流转弱',
                'misjudgment_type': '基本面恶化',
                'repair_logic': '',
            },
        )
        assert result.verdict == 'eliminate'


class TestPoolGroupAssigner:
    def test_high_dividend_has_highest_priority(self):
        assigner = PoolGroupAssigner()
        logic = LogicAnalyzer().analyze(
            {'pb': '0.7', 'pe_ttm': '8', 'dividend_yield': '5.6'},
            {'why_fell': '市场错杀', 'repair_logic': '分红稳定', 'catalyst_clarity': '明确'},
        )
        group = assigner.assign({'pb': '0.7', 'pe_ttm': '8', 'dividend_yield': '5.6'}, logic)
        assert group == PoolGroup.HIGH_DIVIDEND
