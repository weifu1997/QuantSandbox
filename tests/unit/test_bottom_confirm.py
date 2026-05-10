from __future__ import annotations

from backend.services.mx.result import MXServiceResult
from backend.workflows.bottom_confirm.left_side_grader import LeftSideGrader
from backend.workflows.bottom_confirm.runner import BottomConfirmRunner
from backend.workflows.bottom_confirm.schemas import BottomConfirmInput
from backend.workflows.bottom_confirm.search_parser import BottomSearchParser
from backend.workflows.bottom_confirm.stop_loss_calculator import StopLossCalculator
from backend.db.session import session_scope
from backend.repositories import CandidateRepository, WatchlistRepository


class StubDataService:
    def run(self, query: str, timeout: int = 180) -> MXServiceResult:
        symbol = '603166'
        parsed = {
            'symbol': symbol,
            'name': '福达股份',
            'latest_price': '10.0',
            'prior_low_price': '9.8',
            'prior_low_days_ago': '25',
            'ma60_gap_pct': '10',
            'avg_volume_10d': '50',
            'avg_volume_20d': '100',
            'pe_ttm': '12',
            'pb': '0.9',
            'board': '主板',
            'dividend_yield': '2.0',
            'month_return': '-3.0',
        }
        return MXServiceResult(ok=True, tool='mx-data', query=query, parsed=parsed)


class StubSearchService:
    def run(self, query: str, timeout: int = 180) -> MXServiceResult:
        return MXServiceResult(ok=True, tool='mx-search', query=query, parsed={'preview': ['最近30日有营收修复催化，业绩改善预期明确'], 'summary': '行业压制后修复', 'catalyst': '营收修复催化明确'})


class StubMoniService:
    def __init__(self):
        self.queries = []

    def run(self, query: str, timeout: int = 180) -> MXServiceResult:
        self.queries.append(query)
        return MXServiceResult(ok=True, tool='mx-moni', query=query, parsed={'preview': ['模拟买入成功']})


def test_left_side_grader_assigns_a_for_strong_setup():
    grader = LeftSideGrader()
    result = grader.grade({
        'latest_price': '10',
        'prior_low_price': '9.8',
        'prior_low_days_ago': '30',
        'ma60_gap_pct': '12',
        'avg_volume_10d': '50',
        'avg_volume_20d': '100',
        'recent_catalyst': '营收修复',
        'pe_ttm': '12',
    })
    assert result.grade == 'A'
    assert result.score >= 4


def test_stop_loss_calculator_uses_tighter_stop():
    calc = StopLossCalculator()
    result = calc.calculate({'latest_price': '10', 'prior_low_price': '9.8'})
    assert result.stop_loss_price == 9.506
    assert result.reference_low_price == 9.506
    assert result.price_based_stop_loss == 9.2


def test_bottom_search_parser_extracts_clear_catalyst_and_right_side_signal():
    parser = BottomSearchParser()
    result = parser.parse('公司一季报同比增长，订单增加，机构评级: 买入，业绩实现增长。')
    assert result.catalyst_clarity == 'clear'
    assert result.right_side_signal is True
    assert result.catalyst_summary in {'订单增加', '同比增长', '评级: 买入', '业绩实现增长'}


def test_bottom_confirm_runner_builds_moni_limit_buy_query():
    runner = BottomConfirmRunner(data_service=StubDataService(), search_service=StubSearchService(), moni_service=StubMoniService())
    query = runner._build_moni_buy_query({'symbol': '603166', 'latest_price': '10.0'})
    assert query == '买入 603166 价格 10.000 数量 100 股'


def test_bottom_confirm_runner_creates_buy_plan_and_watchlist():
    moni = StubMoniService()
    runner = BottomConfirmRunner(data_service=StubDataService(), search_service=StubSearchService(), moni_service=moni)
    run_id = runner.create_run(BottomConfirmInput(symbols=['603166'], user_id='phase2-test'))
    runner.execute_steps(BottomConfirmInput(symbols=['603166'], user_id='phase2-test'), run_id)

    with session_scope() as s:
        candidates = CandidateRepository(s).list_by_workflow_run(run_id)
        watchlist = WatchlistRepository(s).list_by_workflow_run(run_id)
        assert len(candidates) == 1
        assert candidates[0].data['left_side_grade'] == 'C'
        assert candidates[0].data['action'] == 'watch'
        assert len(watchlist) == 1
        assert watchlist[0].left_side_grade == 'C'
        assert watchlist[0].stop_loss_price is None
    assert moni.queries == []
