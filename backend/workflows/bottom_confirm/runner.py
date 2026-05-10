from __future__ import annotations

from uuid import uuid4

from backend.db.session import session_scope
from backend.models import Candidate, CandidateReview, CandidateStatus, RiskLevel, WatchlistEntry, WorkflowRun, WorkflowRunStatus
from backend.models.watchlist import PositionAge
from backend.models.workflow import WorkflowStepStatus
from backend.models.workflow_step import WorkflowStepRun
from backend.repositories import CandidateRepository, CandidateReviewRepository, WatchlistRepository, WorkflowRunRepository, WorkflowStepRunRepository
from backend.services.mx import DataService, MoniService, SearchService
from backend.utils.time import utcnow
from backend.workflows.bottom_confirm.left_side_grader import LeftSideGrader
from backend.workflows.bottom_confirm.schemas import BottomConfirmInput
from backend.workflows.bottom_confirm.search_parser import BottomSearchParser
from backend.workflows.bottom_confirm.stop_loss_calculator import StopLossCalculator
from backend.workflows.low_value_flow.logic_analyzer import LogicAnalyzer
from backend.workflows.low_value_flow.rules import safe_float
from backend.workflows.low_value_flow.serializer import review_result_from_status
from backend.workflows.low_value_flow.structure_verifier import StructureVerifier
from backend.workflows.types import WorkflowType


class BottomConfirmRunner:
    def __init__(self, data_service: DataService | None = None, search_service: SearchService | None = None, moni_service: MoniService | None = None):
        self.data_service = data_service or DataService()
        self.search_service = search_service or SearchService()
        self.moni_service = moni_service or MoniService()
        self.structure_verifier = StructureVerifier()
        self.logic_analyzer = LogicAnalyzer()
        self.left_side_grader = LeftSideGrader()
        self.stop_loss_calculator = StopLossCalculator()
        self.search_parser = BottomSearchParser()

    def create_run(self, payload: BottomConfirmInput) -> str:
        with session_scope() as s:
            repo = WorkflowRunRepository(s)
            run = repo.create(WorkflowRun(
                user_id=payload.user_id,
                workflow_type=WorkflowType.BOTTOM_CONFIRM.value,
                status=WorkflowRunStatus.RUNNING,
                started_at=utcnow(),
                total_steps=4,
                config=payload.model_dump(),
            ))
            return run.id

    def execute_steps(self, payload: BottomConfirmInput, run_id: str) -> None:
        try:
            items = self._run_step1_data(run_id, payload.symbols)
            search_ready = self._run_step2_search(run_id, items)
            plans = self._run_step3_judgement(run_id, search_ready, payload)
            self._run_step4_moni(run_id, plans)
            self._mark_run_status(run_id, WorkflowRunStatus.COMPLETED)
        except Exception:
            self._mark_run_status(run_id, WorkflowRunStatus.FAILED)
            raise

    def _create_step(self, workflow_run_id: str, step_code: str, step_name: str) -> str:
        step_id = str(uuid4())
        with session_scope() as s:
            WorkflowStepRunRepository(s).create(WorkflowStepRun(
                id=step_id,
                workflow_run_id=workflow_run_id,
                step_code=step_code,
                step_name=step_name,
                status=WorkflowStepStatus.RUNNING,
                started_at=utcnow(),
            ))
        return step_id

    def _finish_step(self, step_id: str, status: WorkflowStepStatus, result_data: dict | None = None, error_message: str | None = None) -> None:
        with session_scope() as s:
            repo = WorkflowStepRunRepository(s)
            step = repo.get(step_id)
            if not step:
                return
            step.status = status
            step.completed_at = utcnow()
            step.result_data = result_data
            step.error_message = error_message

    def _mark_run_status(self, run_id: str, status: WorkflowRunStatus) -> None:
        with session_scope() as s:
            repo = WorkflowRunRepository(s)
            run = repo.get(run_id)
            if not run:
                return
            run.status = status
            if status in {WorkflowRunStatus.COMPLETED, WorkflowRunStatus.FAILED, WorkflowRunStatus.CANCELLED}:
                run.completed_at = utcnow()

    def _extract_bottom_data_from_mx(self, result) -> dict:
        data: dict[str, object] = {}
        raw_json = ((result.raw or {}).get('raw_json') or {}) if result and result.ok else {}
        dto_list = ((((raw_json.get('data') or {}).get('data') or {}).get('searchDataResultDTO') or {}).get('dataTableDTOList') or [])
        for table in dto_list:
            title = str(table.get('title') or '')
            entity = (table.get('entityTagDTO') or {})
            if entity.get('fullName') and not data.get('name'):
                data['name'] = entity.get('fullName')
            values = table.get('table') or {}
            name_map = table.get('nameMap') or {}
            if '成交量' in title or '市净率PB' in title:
                volumes = self._table_series(values, name_map, '成交量')
                closes = self._table_series(values, name_map, '收盘价')
                pbs = self._table_series(values, name_map, '市净率PB')
                pes = self._table_series(values, name_map, '市盈率PE(TTM)')
                if closes:
                    data['latest_price'] = closes[0]
                if pbs:
                    data['pb'] = pbs[0]
                if pes:
                    data['pe_ttm'] = pes[0]
                if len(volumes) >= 10:
                    data['avg_volume_10d'] = self._average_numeric(volumes[:10])
                if len(volumes) >= 17:
                    data['avg_volume_20d'] = self._average_numeric(volumes)
            elif '股息率(TTM)' in title or 'BOLL布林线LOW' in title:
                dividend = self._table_series(values, name_map, '股息率(TTM)')
                boll_low = self._table_series(values, name_map, 'BOLL布林线LOW')
                if dividend:
                    data['dividend_yield'] = dividend[0]
                if boll_low and not data.get('support_price'):
                    data['support_price'] = boll_low[0]
            elif '60日MA' in title:
                ma_series = self._first_metric_series(values)
                if ma_series:
                    data['ma60'] = ma_series[0]
                    latest = safe_float(data.get('latest_price'))
                    ma60 = safe_float(ma_series[0])
                    if latest is not None and latest > 0 and ma60 is not None:
                        data['ma60_gap_pct'] = round(abs(ma60 - latest) / latest * 100, 3)
            elif '历史最低价' in title:
                low_price = self._table_series(values, name_map, '历史最低价')
                low_date = self._table_series(values, name_map, '历史最低价日')
                if low_price:
                    data['prior_low_price'] = low_price[0]
                    data['support_price'] = low_price[0]
                if low_date:
                    data['prior_low_days_ago'] = self._days_since(low_date[0])
            elif '区间涨跌幅' in title or '区间换手率' in title:
                returns = self._table_series(values, name_map, '区间涨跌幅')
                turnovers = self._table_series(values, name_map, '区间换手率')
                if returns:
                    data['month_return'] = returns[1] if len(returns) > 1 else returns[0]
                    recent = safe_float(returns[0])
                    month = safe_float(returns[1]) if len(returns) > 1 else safe_float(returns[0])
                    quarter = safe_float(returns[2]) if len(returns) > 2 else month
                    if recent is not None:
                        data['decline_slope_10d'] = recent
                    if month is not None:
                        data['decline_slope_30d'] = month
                    if recent is not None and month is not None:
                        data['consolidation_range_pct'] = abs(recent - month)
                    if quarter is not None and month is not None:
                        data['consolidation_days'] = 20 if abs(month - quarter) <= 10 else 5
                if turnovers:
                    if len(turnovers) > 0:
                        data['turnover_10_15d'] = turnovers[0]
                    if len(turnovers) > 1:
                        data['turnover_3m'] = turnovers[1]
                    if len(turnovers) > 0:
                        latest_turnover = safe_float(turnovers[0])
                        month_turnover = safe_float(turnovers[1]) if len(turnovers) > 1 else latest_turnover
                        data['volume_breakdown_days'] = 0 if latest_turnover is not None and month_turnover is not None and latest_turnover <= month_turnover * 1.5 else 1
        return data

    @staticmethod
    def _table_series(table: dict, name_map: dict, label: str) -> list:
        for key, mapped_name in name_map.items():
            if str(mapped_name).strip() == label and key in table:
                return list(table[key])
        for key, series in table.items():
            if key == label:
                return list(series)
        return []

    @staticmethod
    def _first_metric_series(table: dict) -> list:
        for key, value in table.items():
            if key != 'headName':
                return list(value)
        return []

    @staticmethod
    def _average_numeric(values: list) -> float | None:
        nums = [safe_float(v) for v in values]
        nums = [v for v in nums if v is not None]
        if not nums:
            return None
        return round(sum(nums) / len(nums), 3)

    @staticmethod
    def _days_since(date_text: str) -> int | None:
        from datetime import datetime
        try:
            dt = datetime.strptime(str(date_text).strip(), '%Y-%m-%d')
            return max((utcnow().date() - dt.date()).days, 0)
        except Exception:
            return None

    def _run_step1_data(self, run_id: str, symbols: list[str]) -> list[dict]:
        step_id = self._create_step(run_id, 'data', 'Step 1 Data')
        items: list[dict] = []
        with session_scope() as s:
            cand_repo = CandidateRepository(s)
            review_repo = CandidateReviewRepository(s)
            for symbol in symbols:
                quote_result = self.data_service.run(f'查询 {symbol} 的现价、前低、前低距今天数、MA60、MA60距离现价百分比、近10日日均量、近20日日均量、PB、PE、最近30日催化', timeout=180)
                structure_result = self.data_service.run(f'查询 {symbol} 的估值、股息率、近1月涨跌幅、10到15日换手率、3个月换手率、支撑位、前低、10日跌速、30日跌速、横盘区间、横盘天数、放量破位天数', timeout=180)
                data = self._extract_bottom_data_from_mx(quote_result)
                data.update({k: v for k, v in self._extract_bottom_data_from_mx(structure_result).items() if v not in (None, '', [])})
                data['symbol'] = symbol
                candidate = cand_repo.create(Candidate(workflow_run_id=run_id, symbol=symbol, name=str(data.get('name') or symbol), status=CandidateStatus.PENDING, reason={'from': 'bottom_confirm'}, data=data))
                review_repo.create(CandidateReview(candidate_id=candidate.id, step_code='data', review_result=review_result_from_status('pass' if (quote_result.ok or structure_result.ok) else 'insufficient'), review_reason='mx_data_loaded' if (quote_result.ok or structure_result.ok) else (quote_result.error_message or structure_result.error_message), review_data=data))
                items.append(data)
        self._finish_step(step_id, WorkflowStepStatus.COMPLETED, result_data={'count': len(items)})
        return items

    def _run_step2_search(self, run_id: str, items: list[dict]) -> list[dict]:
        step_id = self._create_step(run_id, 'search', 'Step 2 Search')
        enriched: list[dict] = []
        with session_scope() as s:
            cand_repo = CandidateRepository(s)
            review_repo = CandidateReviewRepository(s)
            rows = {c.symbol: c for c in cand_repo.list_by_workflow_run(run_id)}
            for item in items:
                symbol = str(item.get('symbol', '')).strip()
                result = self.search_service.run(f'{symbol} 最近30日 营收 利润 催化 事件 趋势 评级', timeout=180)
                merged = dict(item)
                if result.ok and isinstance(result.parsed, dict):
                    merged.update(result.parsed)
                    preview = ' '.join(result.parsed.get('preview') or [])
                    if preview:
                        merged['recent_catalyst'] = preview[:300]
                        parsed_signal = self.search_parser.parse(preview)
                        merged['bottom_search'] = parsed_signal.__dict__
                        merged['recent_catalyst'] = parsed_signal.catalyst_summary or merged['recent_catalyst']
                candidate = rows.get(symbol)
                if candidate:
                    candidate.data = merged
                    review_repo.create(CandidateReview(candidate_id=candidate.id, step_code='search', review_result=review_result_from_status('pass' if result.ok else 'insufficient'), review_reason='mx_search_loaded' if result.ok else result.error_message, review_data=merged))
                enriched.append(merged)
        self._finish_step(step_id, WorkflowStepStatus.COMPLETED, result_data={'count': len(enriched)})
        return enriched

    def _run_step3_judgement(self, run_id: str, items: list[dict], payload: BottomConfirmInput) -> list[dict]:
        step_id = self._create_step(run_id, 'judge', 'Step 3 Left/Right Judgement')
        plans: list[dict] = []
        with session_scope() as s:
            cand_repo = CandidateRepository(s)
            review_repo = CandidateReviewRepository(s)
            rows = {c.symbol: c for c in cand_repo.list_by_workflow_run(run_id)}
            for item in items:
                symbol = str(item.get('symbol', '')).strip()
                candidate = rows.get(symbol)
                structure = self.structure_verifier.verify(item)
                logic = self.logic_analyzer.analyze(item, item)
                search_signal = item.get('bottom_search') or {}
                grade_result = self.left_side_grader.grade(item)
                stop_loss = self.stop_loss_calculator.calculate(item)
                action = 'watch'
                if grade_result.grade == 'A' and payload.left_side_preference:
                    action = 'buy'
                elif grade_result.grade == 'B':
                    action = 'alert'
                if payload.right_side_preference and search_signal.get('right_side_signal') and search_signal.get('catalyst_clarity') == 'clear':
                    action = 'buy' if grade_result.grade in {'A', 'B'} else 'alert'
                plan = {
                    **item,
                    'left_side_grade': grade_result.grade,
                    'left_side_score': grade_result.score,
                    'structure': structure.__dict__,
                    'logic': logic.__dict__,
                    'bottom_search': search_signal,
                    'stop_loss_price': stop_loss.stop_loss_price,
                    'target_price': round((stop_loss.stop_loss_price or 0) * 1.2, 3) if stop_loss.stop_loss_price else None,
                    'action': action,
                }
                if candidate:
                    candidate.status = CandidateStatus.SELECTED if action != 'watch' else CandidateStatus.PENDING
                    candidate.data = plan
                    review_repo.create(CandidateReview(candidate_id=candidate.id, step_code='judge', review_result=review_result_from_status('pass' if action != 'watch' else 'partial'), review_reason=f'left_side_{grade_result.grade.lower()}', review_data=plan))
                plans.append(plan)
        self._finish_step(step_id, WorkflowStepStatus.COMPLETED, result_data={'plans': plans})
        return plans

    def _build_moni_buy_query(self, item: dict) -> str:
        symbol = str(item.get('symbol', '')).strip()
        latest_price = safe_float(item.get('latest_price'))
        quantity = 100
        if latest_price is not None and latest_price > 0:
            return f'买入 {symbol} 价格 {latest_price:.3f} 数量 {quantity} 股'
        return f'市价买入 {symbol} {quantity} 股'

    def _run_step4_moni(self, run_id: str, plans: list[dict]) -> None:
        step_id = self._create_step(run_id, 'moni', 'Step 4 Moni')
        results = []
        with session_scope() as s:
            watch_repo = WatchlistRepository(s)
            for item in plans:
                symbol = str(item.get('symbol', '')).strip()
                action = item.get('action')
                moni_ok = True
                moni_error = None
                if action == 'buy':
                    result = self.moni_service.run(self._build_moni_buy_query(item), timeout=180)
                    moni_ok = result.ok
                    moni_error = result.error_message
                watch_repo.create(WatchlistEntry(
                    workflow_run_id=run_id,
                    symbol=symbol,
                    name=str(item.get('name') or symbol),
                    entry_reason='bottom_confirm_plan',
                    risk_level=RiskLevel.MEDIUM if item.get('left_side_grade') in {'A', 'B'} else RiskLevel.HIGH,
                    catalyst_factors=item.get('recent_catalyst'),
                    board=item.get('board') or None,
                    pe_ttm=str(item.get('pe_ttm', '') or ''),
                    pe_ttm_num=safe_float(item.get('pe_ttm')),
                    pb=str(item.get('pb', '') or ''),
                    pb_num=safe_float(item.get('pb')),
                    latest_price=str(item.get('latest_price', '') or ''),
                    latest_price_num=safe_float(item.get('latest_price')),
                    dividend_yield=str(item.get('dividend_yield', '') or ''),
                    dividend_yield_num=safe_float(item.get('dividend_yield')),
                    month_return=str(item.get('month_return', '') or ''),
                    month_return_num=safe_float(item.get('month_return')),
                    st_flag=str(item.get('st_flag', '') or ''),
                    watch_price_zone='bottom_confirm',
                    position_age=PositionAge.NEW.value,
                    left_side_grade=item.get('left_side_grade'),
                    stop_loss_price=item.get('stop_loss_price'),
                    target_price=item.get('target_price'),
                    buy_date=utcnow() if action == 'buy' else None,
                    catalyst_signal=item.get('recent_catalyst') or None,
                    observation_note=f'action={action}; score={item.get("left_side_score")}',
                ))
                results.append({'symbol': symbol, 'action': action, 'ok': moni_ok, 'error': moni_error})
        has_failure = any(not row['ok'] for row in results if row['action'] == 'buy')
        self._finish_step(step_id, WorkflowStepStatus.FAILED if has_failure else WorkflowStepStatus.COMPLETED, result_data={'results': results})
