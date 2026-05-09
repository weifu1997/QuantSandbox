from __future__ import annotations

from uuid import uuid4
import logging
from typing import Any

from backend.db.session import session_scope
from backend.models import (
    Candidate,
    CandidateReview,
    CandidateStatus,
    WatchlistEntry,
    WorkflowRun,
    WorkflowRunStatus,
)
from backend.models.workflow import WorkflowStepStatus
from backend.models.workflow_step import WorkflowStepRun
from backend.repositories import (
    CandidateRepository,
    CandidateReviewRepository,
    WatchlistRepository,
    WorkflowRunRepository,
    WorkflowStepRunRepository,
)
from backend.services.mx import DataService, SearchService, XuanguService, ZixuanService
from backend.utils.time import utcnow
from backend.workflows.common.batching import chunked
from backend.workflows.low_value_flow.catalyst_extractor import CatalystExtractor
from backend.workflows.low_value_flow.entry_reason_builder import EntryReasonBuilder
from backend.workflows.low_value_flow.price_zone_builder import PriceZoneBuilder
from backend.workflows.low_value_flow.risk_assessor import RiskAssessor
from backend.workflows.low_value_flow.rules import should_reject_in_quick_risk, structure_decision_from_data
from backend.workflows.low_value_flow.schemas import LowValueRunInput, build_default_query
from backend.workflows.low_value_flow.serializer import review_result_from_status
from backend.workflows.types import WorkflowType

logger = logging.getLogger(__name__)


class LowValueWorkflowRunner:
    def __init__(
        self,
        xuangu_service: XuanguService | None = None,
        data_service: DataService | None = None,
        search_service: SearchService | None = None,
        zixuan_service: ZixuanService | None = None,
        batch_size: int = 5,
    ):
        self.xuangu_service = xuangu_service or XuanguService()
        self.data_service = data_service or DataService()
        self.search_service = search_service or SearchService()
        self.zixuan_service = zixuan_service or ZixuanService()
        self.batch_size = batch_size
        self.risk_assessor = RiskAssessor()
        self.entry_reason_builder = EntryReasonBuilder(self.risk_assessor)
        self.price_zone_builder = PriceZoneBuilder(self.data_service, self.risk_assessor)
        self.catalyst_extractor = CatalystExtractor()

    def _load_candidate_reviews(self, candidate) -> dict[str, CandidateReview]:
        reviews = getattr(candidate, 'reviews', None) or []
        return {r.step_code: r for r in reviews}

    def create_run(self, payload: LowValueRunInput) -> str:
        query = payload.custom_query.strip() if payload.custom_query else build_default_query(payload.template)
        return self._create_workflow_run(payload, query)

    def execute_steps(self, payload: LowValueRunInput, run_id: str) -> None:
        try:
            query = payload.custom_query.strip() if payload.custom_query else build_default_query(payload.template)
            step1 = self._run_step1_xuangu(run_id, query)
            survivors = self._run_step1_5_risk(run_id, step1)
            structure_passed = self._run_step2_data(run_id, survivors)
            logic_passed = self._run_step3_search(run_id, structure_passed)
            self._run_step4_zixuan(run_id, logic_passed)
            self._mark_run_status(run_id, WorkflowRunStatus.COMPLETED)
        except Exception:
            self._mark_run_status(run_id, WorkflowRunStatus.FAILED)
            raise

    def _create_workflow_run(self, payload: LowValueRunInput, query: str) -> str:
        with session_scope() as s:
            repo = WorkflowRunRepository(s)
            run = repo.create(
                WorkflowRun(
                    user_id=payload.user_id,
                    workflow_type=WorkflowType.LOW_VALUE.value,
                    status=WorkflowRunStatus.RUNNING,
                    started_at=utcnow(),
                    total_steps=5,
                    config={
                        'use_default_template': payload.use_default_template,
                        'custom_query': payload.custom_query,
                        'resolved_query': query,
                    },
                )
            )
            return run.id

    def _create_step(self, workflow_run_id: str, step_code: str, step_name: str) -> str:
        step_id = str(uuid4())
        with session_scope() as s:
            repo = WorkflowStepRunRepository(s)
            repo.create(
                WorkflowStepRun(
                    id=step_id,
                    workflow_run_id=workflow_run_id,
                    step_code=step_code,
                    step_name=step_name,
                    status=WorkflowStepStatus.RUNNING,
                    started_at=utcnow(),
                )
            )
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

    def _run_step1_xuangu(self, run_id: str, query: str) -> list[dict]:
        step_id = self._create_step(run_id, 'xuangu', 'Step 1 Xuangu')
        result = self.xuangu_service.run(query, timeout=300)
        if not result.ok:
            self._finish_step(step_id, WorkflowStepStatus.FAILED, error_message=result.error_message)
            raise RuntimeError(result.error_message or 'Step1 failed')

        candidates = result.parsed.get('candidates', [])
        with session_scope() as s:
            repo = CandidateRepository(s)
            for item in candidates:
                repo.create(
                    Candidate(
                        workflow_run_id=run_id,
                        symbol=str(item.get('symbol', '')).strip(),
                        name=str(item.get('name', '')).strip() or None,
                        status=CandidateStatus.PENDING,
                        reason={'from': 'xuangu'},
                        data=item,
                    )
                )
        self._finish_step(step_id, WorkflowStepStatus.COMPLETED, result_data=result.parsed)
        return candidates

    def _run_step1_5_risk(self, run_id: str, candidates: list[dict]) -> list[dict]:
        step_id = self._create_step(run_id, 'risk', 'Step 1.5 Quick Risk')
        survivors: list[dict] = []
        rejected: list[dict] = []
        with session_scope() as s:
            cand_repo = CandidateRepository(s)
            review_repo = CandidateReviewRepository(s)
            rows = {c.symbol: c for c in cand_repo.list_by_workflow_run(run_id)}
            for item in candidates:
                symbol = str(item.get('symbol', '')).strip()
                candidate = rows.get(symbol)
                if not candidate:
                    continue
                reject, reason = should_reject_in_quick_risk(item)
                if reject:
                    candidate.status = CandidateStatus.ELIMINATED
                    candidate.reason = {'step': 'risk', 'reason': reason}
                    rejected.append({'symbol': symbol, 'reason': reason})
                    review_repo.create(
                        CandidateReview(
                            candidate_id=candidate.id,
                            step_code='risk',
                            review_result=review_result_from_status('fail'),
                            review_reason=reason,
                            review_data=item,
                        )
                    )
                else:
                    candidate.status = CandidateStatus.SELECTED
                    survivors.append(item)
                    review_repo.create(
                        CandidateReview(
                            candidate_id=candidate.id,
                            step_code='risk',
                            review_result=review_result_from_status('pass'),
                            review_reason='quick_risk_passed',
                            review_data=item,
                        )
                    )
        self._finish_step(step_id, WorkflowStepStatus.COMPLETED, result_data={'survivors': survivors, 'rejected': rejected})
        return survivors

    def _run_step2_data(self, run_id: str, candidates: list[dict]) -> list[dict]:
        step_id = self._create_step(run_id, 'data', 'Step 2 Data')
        if not candidates:
            self._finish_step(step_id, WorkflowStepStatus.COMPLETED, result_data={'message': 'no candidates for data'})
            return []
        passed: list[dict] = []
        with session_scope() as s:
            cand_repo = CandidateRepository(s)
            review_repo = CandidateReviewRepository(s)
            rows = {c.symbol: c for c in cand_repo.list_by_workflow_run(run_id)}
            for batch in chunked(candidates, self.batch_size):
                names = '、'.join([f"{x.get('name', '')}({x.get('symbol', '')})" for x in batch])
                result = self.data_service.run(f"查询 {names} 的估值、股息率、近1月涨跌幅", timeout=180)
                ok = result.ok
                for item in batch:
                    symbol = str(item.get('symbol', '')).strip()
                    candidate = rows.get(symbol)
                    if not candidate:
                        continue
                    if ok:
                        candidate.status = CandidateStatus.SELECTED
                        passed.append(item)
                        review_repo.create(CandidateReview(candidate_id=candidate.id, step_code='data', review_result=review_result_from_status('pass'), review_reason='data_completed', review_data=result.parsed))
                    else:
                        candidate.status = CandidateStatus.INSUFFICIENT_DATA
                        review_repo.create(CandidateReview(candidate_id=candidate.id, step_code='data', review_result=review_result_from_status('insufficient'), review_reason=result.error_message, review_data={}))
        self._finish_step(step_id, WorkflowStepStatus.COMPLETED, result_data={'passed_count': len(passed)})
        return passed

    def _run_step3_search(self, run_id: str, candidates: list[dict]) -> list[dict]:
        step_id = self._create_step(run_id, 'search', 'Step 3 Search')
        if not candidates:
            self._finish_step(step_id, WorkflowStepStatus.COMPLETED, result_data={'message': 'no candidates for search'})
            return []
        passed: list[dict] = []
        with session_scope() as s:
            cand_repo = CandidateRepository(s)
            review_repo = CandidateReviewRepository(s)
            rows = {c.symbol: c for c in cand_repo.list_by_workflow_run(run_id)}
            for item in candidates:
                symbol = str(item.get('symbol', '')).strip()
                candidate = rows.get(symbol)
                if not candidate:
                    continue
                query = f"{item.get('name', symbol)} 最近公告 业绩 分红 回购 增持 行业催化 风险点"
                result = self.search_service.run(query, timeout=180)
                if result.ok:
                    candidate.status = CandidateStatus.SELECTED
                    passed.append(item)
                    review_repo.create(CandidateReview(candidate_id=candidate.id, step_code='search', review_result=review_result_from_status('pass'), review_reason='search_completed', review_data=result.parsed))
                else:
                    candidate.status = CandidateStatus.INSUFFICIENT_DATA
                    review_repo.create(CandidateReview(candidate_id=candidate.id, step_code='search', review_result=review_result_from_status('insufficient'), review_reason=result.error_message, review_data={}))
        self._finish_step(step_id, WorkflowStepStatus.COMPLETED, result_data={'passed_count': len(passed)})
        return passed

    def _run_step4_zixuan(self, run_id: str, candidates: list[dict]) -> None:
        step_id = self._create_step(run_id, 'zixuan', 'Step 4 Zixuan')
        if not candidates:
            self._finish_step(step_id, WorkflowStepStatus.COMPLETED, result_data={'message': 'no candidates for watchlist'})
            return
        with session_scope() as s:
            watch_repo = WatchlistRepository(s)
            cand_repo = CandidateRepository(s)
            rows = {c.symbol: c for c in cand_repo.list_by_workflow_run(run_id)}
            add_results = []
            for item in candidates:
                symbol = str(item.get('symbol', '')).strip()
                name = str(item.get('name', symbol))
                candidate = rows.get(symbol)
                query = f"把{name}添加到我的自选股列表"
                result = self.zixuan_service.run(query)
                add_results.append({'symbol': symbol, 'ok': result.ok, 'error': result.error_message})
                if result.ok and candidate:
                    reviews = self._load_candidate_reviews(candidate)
                    search_review = reviews.get('search')
                    base_data = dict(candidate.data) if isinstance(candidate.data, dict) else dict(item)
                    base_data['board'] = self.entry_reason_builder.derive_board(symbol, base_data.get('board'))
                    catalyst_factors = self.catalyst_extractor.derive_catalyst_factors(getattr(search_review, 'review_data', None))
                    watch_repo.create(
                        WatchlistEntry(
                            workflow_run_id=run_id,
                            symbol=symbol,
                            name=name,
                            entry_reason=self.entry_reason_builder.derive_entry_reason(base_data, catalyst_factors),
                            risk_level=self.risk_assessor.derive_risk_level(base_data),
                            catalyst_factors=catalyst_factors,
                            board=base_data.get('board') or None,
                            pe_ttm=str(base_data.get('pe_ttm', '') or ''),
                            pe_ttm_num=self.risk_assessor.safe_float(base_data.get('pe_ttm')),
                            pb=str(base_data.get('pb', '') or ''),
                            pb_num=self.risk_assessor.safe_float(base_data.get('pb')),
                            latest_price=str(base_data.get('latest_price', '') or ''),
                            latest_price_num=self.risk_assessor.safe_float(base_data.get('latest_price')),
                            dividend_yield=str(base_data.get('dividend_yield', '') or ''),
                            dividend_yield_num=self.risk_assessor.safe_float(base_data.get('dividend_yield')),
                            month_return=str(base_data.get('month_return', '') or ''),
                            month_return_num=self.risk_assessor.safe_float(base_data.get('month_return')),
                            st_flag=str(base_data.get('st_flag', '') or ''),
                            watch_price_zone=self.price_zone_builder.derive_watch_price_zone(name, symbol, base_data),
                        )
                    )
        has_failure = any(not x['ok'] for x in add_results)
        self._finish_step(step_id, WorkflowStepStatus.FAILED if has_failure else WorkflowStepStatus.COMPLETED, result_data={'results': add_results})
