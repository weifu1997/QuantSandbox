from __future__ import annotations

from backend.services.mx.result import MXServiceResult
from backend.workflows.low_value_flow.risk_enricher import RiskEnricher
from backend.workflows.low_value_flow.runner import LowValueWorkflowRunner
from backend.workflows.low_value_flow.schemas import LowValueRunInput
from backend.db.session import session_scope
from backend.repositories import CandidateRepository, CandidateReviewRepository


class StubDataService:
    def run(self, query: str, timeout: int = 180) -> MXServiceResult:
        return MXServiceResult(
            ok=True,
            tool='mx-data',
            query=query,
            raw={
                'raw_json': {
                    'data': {
                        'data': {
                            'searchDataResultDTO': {
                                'dataTableDTOList': [
                                    {
                                        'title': '福达股份(603166.SH)的审计意见类别',
                                        'field': {'returnName': '审计意见类别'},
                                        'table': {
                                            'headName': ['2025年报', '2024年报'],
                                            '100000000000005': ['标准无保留意见', '标准无保留意见'],
                                        },
                                    },
                                    {
                                        'title': '福达股份(603166.SH)违规(2025-05-10~2026-05-10)',
                                        'field': {'returnName': '违规', 'returnCode': 'RPT_HSF9_OP_VIOLATION'},
                                        'table': {
                                            'headName': ['违规行为', '处分措施', '处理人', '违规类型', '处罚对象', '处分类型', '币种'],
                                            '0': ['未及时披露重大事件', '监管警示', '上交所', '未依法履行其他职责', '福达股份', '监管措施', '人民币'],
                                        },
                                    },
                                ]
                            }
                        }
                    }
                }
            },
        )


class StubRunnerDataService:
    def run(self, query: str, timeout: int = 180) -> MXServiceResult:
        return MXServiceResult(
            ok=True,
            tool='mx-data',
            query=query,
            raw={
                'raw_json': {
                    'data': {
                        'data': {
                            'searchDataResultDTO': {
                                'dataTableDTOList': [
                                    {
                                        'title': '福达股份(603166.SH)的审计意见类别',
                                        'field': {'returnName': '审计意见类别'},
                                        'table': {
                                            'headName': ['2025年报', '2024年报'],
                                            '100000000000005': ['标准无保留意见', '标准无保留意见'],
                                        },
                                    }
                                ]
                            }
                        }
                    }
                }
            },
        )


class StubRunnerDataService:
    def run(self, query: str, timeout: int = 180) -> MXServiceResult:
        return MXServiceResult(
            ok=True,
            tool='mx-data',
            query=query,
            raw={
                'raw_json': {
                    'data': {
                        'data': {
                            'searchDataResultDTO': {
                                'dataTableDTOList': [
                                    {
                                        'title': '福达股份(603166.SH)的审计意见类别',
                                        'field': {'returnName': '审计意见类别'},
                                        'table': {
                                            'headName': ['2025年报', '2024年报'],
                                            '100000000000005': ['标准无保留意见', '标准无保留意见'],
                                        },
                                    }
                                ]
                            }
                        }
                    }
                }
            },
        )


class StubSearchService:
    def __init__(self, stdout: str = '') -> None:
        self.stdout = stdout or '公司 2025 年度财务报告被出具无保留意见审计报告；收到监管警示，涉及未及时披露。'

    def run(self, query: str, timeout: int = 180) -> MXServiceResult:
        return MXServiceResult(
            ok=True,
            tool='mx-search',
            query=query,
            raw={'stdout': self.stdout},
            parsed={'preview': [self.stdout]},
        )


class StubXuanguService:
    def run(self, query: str, timeout: int = 300) -> MXServiceResult:
        return MXServiceResult(
            ok=True,
            tool='mx-xuangu',
            query=query,
            parsed={
                'candidates': [
                    {
                        'symbol': '603166',
                        'name': '福达股份',
                        'board': '主板',
                        'pe_ttm': '31.38',
                        'pb': '3.6164',
                        'latest_price': '14.60',
                        'dividend_yield': '0.6754',
                        'month_return': '7.83',
                        'st_flag': '否',
                        'revenue_yoy': '6.9516',
                        'revenue_growth': '6.9154',
                        'profit_yoy': '10.21',
                        'net_profit_change': '60.86',
                        'current_ratio': '1.0871',
                        'quick_ratio': '0.779',
                        'audit_opinion': '',
                        'regulatory_inquiry': '',
                        'risk_flags': [],
                    }
                ]
            },
        )


def test_risk_enricher_extracts_audit_and_regulatory_flags():
    enricher = RiskEnricher(data_service=StubDataService(), search_service=StubSearchService())
    result = enricher.enrich({'symbol': '603166', 'name': '福达股份'})

    assert result.audit_opinion == '标准无保留意见'
    assert '监管警示' in result.regulatory_inquiry
    assert '未依法履行其他职责' in result.regulatory_inquiry
    assert '监管警示' in result.risk_flags
    assert '监管措施' in result.risk_flags
    assert '信披异常' in result.risk_flags


def test_risk_enricher_falls_back_to_mx_search_when_mx_data_missing():
    class EmptyDataService:
        def run(self, query: str, timeout: int = 180) -> MXServiceResult:
            return MXServiceResult(ok=True, tool='mx-data', query=query, raw={'raw_json': {'data': {'data': {'searchDataResultDTO': {'dataTableDTOList': []}}}}})

    search = StubSearchService('公司最近三年财务会计报告被出具无保留意见审计报告；曾收到监管警示并因未及时披露收到问询函。')
    enricher = RiskEnricher(data_service=EmptyDataService(), search_service=search)
    result = enricher.enrich({'symbol': '603166', 'name': '福达股份'})

    assert result.audit_opinion == '标准无保留意见'
    assert '监管警示' in result.regulatory_inquiry
    assert '问询函' in result.regulatory_inquiry
    assert '监管警示' in result.risk_flags
    assert '监管问询' in result.risk_flags
    assert 'audit fallback from mx-search' in result.source_notes


def test_runner_step1_5_applies_risk_enrichment_to_candidate():
    runner = LowValueWorkflowRunner(xuangu_service=StubXuanguService(), data_service=StubRunnerDataService(), search_service=StubSearchService())
    run_id = runner.create_run(LowValueRunInput(use_default_template=True, custom_query='福达股份', user_id='risk-enrich-test'))
    step1 = runner._run_step1_xuangu(run_id, '福达股份')
    survivors = runner._run_step1_5_risk(run_id, step1)

    assert len(survivors) == 1
    enriched = survivors[0]
    assert enriched['audit_opinion'] == '标准无保留意见'
    assert enriched['regulatory_inquiry'] == '监管警示；未及时披露'
    assert enriched['risk_flags'] == ['监管警示', '信披异常']

    with session_scope() as s:
        candidate = CandidateRepository(s).list_by_workflow_run(run_id)[0]
        review = CandidateReviewRepository(s).list_by_candidate(candidate.id)[0]
        assert candidate.data['audit_opinion'] == '标准无保留意见'
        assert candidate.data['regulatory_inquiry'] == '监管警示；未及时披露'
        assert review.review_data['risk_enrichment']['audit_opinion'] == '标准无保留意见'
        assert 'regulatory fallback from mx-search' in review.review_data['risk_enrichment']['source_notes']
