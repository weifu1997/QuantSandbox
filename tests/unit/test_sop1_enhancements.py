from __future__ import annotations

from backend.models.watchlist import PoolGroup
from backend.workflows.low_value_flow.logic_analyzer import LogicAnalyzer
from backend.workflows.low_value_flow.pool_group_assigner import PoolGroupAssigner
from backend.workflows.low_value_flow.runner import LowValueWorkflowRunner
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

    def test_warning_risk_flags_do_not_hard_reject(self):
        result = quick_risk_decision({
            'st_flag': '否',
            'pe_ttm': '10',
            'revenue_yoy': '5',
            'revenue_growth': '4',
            'profit_yoy': '3',
            'net_profit_change': '2',
            'current_ratio': '1.5',
            'quick_ratio': '1.1',
            'audit_opinion': '标准无保留意见',
            'regulatory_inquiry': '监管警示；未及时披露重大事件',
            'risk_flags': ['监管警示', '监管措施', '信披异常'],
        })
        assert result.reject is False
        assert result.data_insufficient is False

    def test_hard_risk_flags_still_reject(self):
        result = quick_risk_decision({
            'st_flag': '否',
            'pe_ttm': '10',
            'revenue_yoy': '5',
            'revenue_growth': '4',
            'profit_yoy': '3',
            'net_profit_change': '2',
            'current_ratio': '1.5',
            'quick_ratio': '1.1',
            'audit_opinion': '标准无保留意见',
            'regulatory_inquiry': '',
            'risk_flags': ['重大诉讼'],
        })
        assert result.reject is True
        assert result.reason == '其他重大风险'


class TestStructureVerifier:
    def test_runner_extracts_structure_fields_from_raw_json(self):
        runner = LowValueWorkflowRunner()
        result = type('R', (), {
            'ok': True,
            'raw': {
                'raw_json': {
                    'data': {
                        'data': {
                            'searchDataResultDTO': {
                                'dataTableDTOList': [
                                    {
                                        'title': '股息率(TTM) / BOLL布林线LOW',
                                        'entityTagDTO': {'fullName': '福达股份'},
                                        'nameMap': {'c1': '股息率(TTM)', 'c2': 'BOLL布林线LOW'},
                                        'table': {'c1': ['1.35%'], 'c2': ['12.41']},
                                    },
                                    {
                                        'title': '区间涨跌幅 / 区间换手率',
                                        'nameMap': {'r': '区间涨跌幅', 't': '区间换手率'},
                                        'table': {'r': ['6.881%', '3.642%', '8.0%'], 't': ['4.728%', '17.88%']},
                                    },
                                ]
                            }
                        }
                    }
                }
            }
        })()
        extracted = runner._extract_structure_data_from_mx(result)
        assert extracted['support_price'] == '12.41'
        assert extracted['turnover_10_15d'] == '4.728%'
        assert extracted['turnover_3m'] == '17.88%'
        assert extracted['decline_slope_10d'] == 6.881
        assert extracted['decline_slope_30d'] == 3.642
        assert extracted['volume_breakdown_days'] == 0

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

    def test_doubt_when_preview_contains_positive_and_negative_signals(self):
        analyzer = LogicAnalyzer()
        result = analyzer.analyze(
            {'pb': '3.6', 'pe_ttm': '31.38', 'dividend_yield': '1.35%'},
            {
                'preview': [
                    '一季度国内乘用车市场表现相对疲软，同比呈现两位数下滑。',
                    '公司积极把握发电市场增量需求，实现营业收入同比增长 6.95%。',
                    '公司未来十二个月内将根据业务发展情况确定是否实施其他再融资计划。',
                ]
            },
        )
        assert result.verdict == 'doubt'
        assert result.why_fell
        assert result.repair_logic
        assert result.catalyst_clarity == '清晰'
        assert '疲软' in result.risk_points

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
