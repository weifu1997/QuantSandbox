from __future__ import annotations

from datetime import datetime
from uuid import uuid4
import logging
from typing import Any

from backend.db.session import session_scope
from backend.models import (
    Candidate,
    CandidateReview,
    CandidateStatus,
    RiskLevel,
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
from backend.workflows.common.batching import chunked
from backend.workflows.low_value_flow.rules import should_reject_in_quick_risk, structure_decision_from_data
from backend.workflows.low_value_flow.schemas import LowValueRunInput, build_default_query
from backend.workflows.low_value_flow.serializer import review_result_from_status
from backend.workflows.types import WorkflowType

logger = logging.getLogger(__name__)

CATALYST_KEYWORDS = {
    "分红": "高分红",
    "回购": "回购",
    "增持": "增持",
    "业绩": "业绩改善",
    "预增": "业绩改善",
    "扭亏": "业绩改善",
    "中标": "订单催化",
    "合同": "订单催化",
    "涨价": "价格催化",
    "景气": "行业景气",
    "扩产": "产能扩张",
    "新产能": "产能扩张",
    "新品": "新品催化",
    "创新药": "产品催化",
    "改革": "改革催化",
}


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

    @staticmethod
    def _safe_float(value: object) -> float | None:
        try:
            if value is None or value == "":
                return None
            s = str(value).replace('%', '').replace('元', '').replace('倍', '').replace(',', '').strip()
            return float(s)
        except Exception:
            return None

    def _derive_risk_level(self, candidate_data: dict | None) -> RiskLevel:
        data = candidate_data or {}
        pb = self._safe_float(data.get('pb'))
        pe = self._safe_float(data.get('pe_ttm'))
        div = self._safe_float(data.get('dividend_yield'))
        month_ret = self._safe_float(data.get('month_return'))

        score = 0
        if pb is not None:
            if pb <= 1.0:
                score += 1
            elif pb >= 1.4:
                score -= 1
        if pe is not None:
            if 0 < pe <= 15:
                score += 1
            elif pe >= 18:
                score -= 1
        if div is not None:
            if div >= 3:
                score += 1
            elif div < 2:
                score -= 1
        if month_ret is not None:
            if -15 <= month_ret <= -5:
                score += 1
            elif month_ret < -20:
                score -= 2

        if score >= 2:
            return RiskLevel.LOW
        if score <= -1:
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM

    @staticmethod
    def _derive_board(symbol: str, explicit_board: str | None = None) -> str:
        board = str(explicit_board or '').strip()
        if board and board not in {'SH', 'SZ'}:
            return board
        code = str(symbol or '').strip().lower()
        if code.startswith(('sh', 'sz')):
            code = code[2:]
        if len(code) >= 2:
            if code.startswith('68'):
                return '科创板'
            if code.startswith('30'):
                return '创业板'
            if code.startswith(('60', '00', '001', '002')):
                return '主板'
            if code.startswith(('4', '8', '92')):
                return '北交所'
        return board

    def _extract_latest_snapshot(self, sec_name: str, symbol: str) -> dict[str, float | str] | None:
        query = f"{sec_name or symbol} 最新价 市净率"
        try:
            result = self.data_service.run(query, timeout=120)
            raw = (result.parsed or {}).get('raw_json') if result.ok else None
            data = ((raw or {}).get('data') or {}).get('data', {})
            tables = ((data.get('searchDataResultDTO') or {}).get('dataTableDTOList') or [])
            if not tables:
                return None
            table = tables[0]
            raw_table = table.get('rawTable') or {}
            name_map = table.get('nameMap') or {}
            latest_price = None
            latest_pb = None
            dates = raw_table.get('headName') or []
            for code, values in raw_table.items():
                if code == 'headName' or not values:
                    continue
                label = name_map.get(code, '')
                first = values[0]
                if '收盘价' in label or '最新价' in label:
                    latest_price = self._safe_float(first)
                if '市净率' in label or label == 'PB' or 'PB' in label:
                    latest_pb = self._safe_float(first)
            if latest_price is None:
                return None
            return {
                'price': latest_price,
                'pb': latest_pb,
                'date': dates[0] if dates else '',
            }
        except Exception as e:
            logger.warning('fetch latest snapshot failed for %s %s: %s', sec_name, symbol, e)
            return None

    def _derive_watch_price_zone(self, sec_name: str, symbol: str, candidate_data: dict | None) -> str:
        data = candidate_data or {}
        month_ret = self._safe_float(data.get('month_return'))
        div = self._safe_float(data.get('dividend_yield'))
        snapshot = self._extract_latest_snapshot(sec_name, symbol)

        price = None
        current_pb = None
        if snapshot:
            price = self._safe_float(snapshot.get('price'))
            current_pb = self._safe_float(snapshot.get('pb'))

        if price is None:
            for key in ('latest_price', 'price', 'current_price', 'close_price', 'close'):
                price = self._safe_float(data.get(key))
                if price is not None:
                    break
        if current_pb is None:
            for key in ('pb', 'pb_ratio', 'current_pb'):
                current_pb = self._safe_float(data.get(key))
                if current_pb is not None:
                    break

        if price is not None and current_pb is not None and current_pb > 0:
            low_pb = current_pb * 0.95
            high_pb = current_pb * 1.05
            low_price = price * low_pb / current_pb
            high_price = price * high_pb / current_pb
            if low_price > high_price:
                low_price, high_price = high_price, low_price
            extra = []
            if month_ret is not None and month_ret <= -10:
                extra.append('回撤较深')
            if div is not None and div >= 3:
                extra.append('高股息')
            suffix = f"（PB {low_pb:.2f}~{high_pb:.2f}）"
            if extra:
                suffix += '，' + ' / '.join(extra)
            return f"{low_price:.2f}~{high_price:.2f} 元{suffix}"

        # fallback when latest price unavailable — build zone-style description from hints
        zone_parts: list[str] = []
        if month_ret is not None:
            if month_ret <= -10:
                zone_parts.append('回撤后观察价格区间')
            elif month_ret < 0:
                zone_parts.append('现价附近观察价格区间')
        if div is not None and div >= 3:
            zone_parts.append('高股息支撑')
        if not zone_parts:
            return '现价附近观察价格区间'
        return ' / '.join(zone_parts[:2])

    def _derive_catalyst_factors(self, search_review_data: dict | list | str | None) -> list[str]:
        text_parts: list[str] = []
        if isinstance(search_review_data, dict):
            preview = search_review_data.get('preview')
            if isinstance(preview, list):
                text_parts.extend(str(x) for x in preview[:40])
            else:
                for v in search_review_data.values():
                    if isinstance(v, list):
                        text_parts.extend(str(x) for x in v[:20])
                    elif isinstance(v, str):
                        text_parts.append(v)
        elif isinstance(search_review_data, list):
            text_parts.extend(str(x) for x in search_review_data[:40])
        elif isinstance(search_review_data, str):
            text_parts.append(search_review_data)
        text = '\n'.join(text_parts)

        found: list[str] = []
        for kw, label in CATALYST_KEYWORDS.items():
            if kw in text and label not in found:
                found.append(label)
        return found[:4]

    def _derive_entry_reason(self, candidate_data: dict | None, catalysts: list[str]) -> str:
        data = candidate_data or {}
        parts: list[str] = []
        pb = self._safe_float(data.get('pb'))
        pe = self._safe_float(data.get('pe_ttm'))
        div = self._safe_float(data.get('dividend_yield'))
        month_ret = self._safe_float(data.get('month_return'))
        if pb is not None:
            parts.append(f'PB {pb:.2f}')
        if pe is not None:
            parts.append(f'PE {pe:.2f}')
        if div is not None:
            parts.append(f'股息率 {div:.2f}%')
        if month_ret is not None:
            parts.append(f'近1月 {month_ret:.2f}%')
        if catalysts:
            parts.append('催化: ' + ' / '.join(catalysts[:2]))
        return '；'.join(parts) or '低估发现流入池'

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
                    started_at=datetime.utcnow(),
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
                    started_at=datetime.utcnow(),
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
            step.completed_at = datetime.utcnow()
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
                run.completed_at = datetime.utcnow()

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
                    base_data['board'] = self._derive_board(symbol, base_data.get('board'))
                    catalyst_factors = self._derive_catalyst_factors(getattr(search_review, 'review_data', None))
                    watch_repo.create(
                        WatchlistEntry(
                            workflow_run_id=run_id,
                            symbol=symbol,
                            name=name,
                            entry_reason=self._derive_entry_reason(base_data, catalyst_factors),
                            risk_level=self._derive_risk_level(base_data),
                            catalyst_factors=catalyst_factors,
                            board=base_data.get('board') or None,
                            pe_ttm=str(base_data.get('pe_ttm', '') or ''),
                            pb=str(base_data.get('pb', '') or ''),
                            latest_price=str(base_data.get('latest_price', '') or ''),
                            dividend_yield=str(base_data.get('dividend_yield', '') or ''),
                            month_return=str(base_data.get('month_return', '') or ''),
                            st_flag=str(base_data.get('st_flag', '') or ''),
                            watch_price_zone=self._derive_watch_price_zone(name, symbol, base_data),
                        )
                    )
        has_failure = any(not x['ok'] for x in add_results)
        self._finish_step(step_id, WorkflowStepStatus.FAILED if has_failure else WorkflowStepStatus.COMPLETED, result_data={'results': add_results})
