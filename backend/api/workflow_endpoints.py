from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.api.schemas import LowValueRunRequest, WatchlistUpdateRequest
from backend.db.session import session_scope
from backend.models import RiskLevel
from backend.repositories import (
    CandidateRepository,
    WatchlistRepository,
    WorkflowRunRepository,
    WorkflowStepRunRepository,
)
from backend.services.mx import DataService, SearchService, XuanguService, ZixuanService
from backend.workflows.low_value_flow.runner import LowValueWorkflowRunner
from backend.workflows.low_value_flow.schemas import LowValueRunInput

router = APIRouter(prefix="/api", tags=["workflow"])


def _runner(batch_size: int = 5) -> LowValueWorkflowRunner:
    return LowValueWorkflowRunner(
        xuangu_service=XuanguService(),
        data_service=DataService(),
        search_service=SearchService(),
        zixuan_service=ZixuanService(),
        batch_size=batch_size,
    )


def _serialize_run(run) -> dict[str, Any]:
    return {
        "id": run.id,
        "user_id": run.user_id,
        "workflow_type": getattr(run, "workflow_type", None),
        "status": run.status.value if hasattr(run.status, "value") else str(run.status),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "total_steps": run.total_steps,
        "config": run.config,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


def _serialize_step(step) -> dict[str, Any]:
    return {
        "id": step.id,
        "workflow_run_id": step.workflow_run_id,
        "step_code": step.step_code,
        "step_name": step.step_name,
        "status": step.status.value if hasattr(step.status, "value") else str(step.status),
        "started_at": step.started_at.isoformat() if step.started_at else None,
        "completed_at": step.completed_at.isoformat() if step.completed_at else None,
        "result_data": step.result_data,
        "error_message": step.error_message,
    }


def _serialize_candidate(candidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "symbol": candidate.symbol,
        "name": candidate.name,
        "status": candidate.status.value if hasattr(candidate.status, "value") else str(candidate.status),
        "reason": candidate.reason,
        "data": candidate.data,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
    }


def _serialize_watchlist(entry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "workflow_run_id": entry.workflow_run_id,
        "symbol": entry.symbol,
        "name": entry.name,
        "entry_reason": entry.entry_reason,
        "risk_level": entry.risk_level.value if hasattr(entry.risk_level, "value") else str(entry.risk_level),
        "catalyst_factors": entry.catalyst_factors,
        "board": getattr(entry, 'board', None),
        "pe_ttm": getattr(entry, 'pe_ttm', None),
        "pb": getattr(entry, 'pb', None),
        "latest_price": getattr(entry, 'latest_price', None),
        "dividend_yield": getattr(entry, 'dividend_yield', None),
        "month_return": getattr(entry, 'month_return', None),
        "st_flag": getattr(entry, 'st_flag', None),
        "metrics": {
            "pe_ttm": getattr(entry, 'pe_ttm_num', None),
            "pb": getattr(entry, 'pb_num', None),
            "latest_price": getattr(entry, 'latest_price_num', None),
            "dividend_yield": getattr(entry, 'dividend_yield_num', None),
            "month_return": getattr(entry, 'month_return_num', None),
        },
        "watch_price_zone": entry.watch_price_zone,
        "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


@router.post("/workflows/low-value/run")
def run_low_value(payload: LowValueRunRequest):
    runner = _runner(batch_size=payload.batch_size)
    run_input = LowValueRunInput(
        use_default_template=payload.use_default_template,
        custom_query=payload.custom_query,
        user_id=payload.user_id,
    )
    run_id = runner.create_run(run_input)
    threading.Thread(target=_run_workflow_async, args=(runner, run_input, run_id), daemon=True).start()
    return {"status": "success", "run_id": run_id}


def _run_workflow_async(runner: LowValueWorkflowRunner, run_input: LowValueRunInput, run_id: str):
    runner.execute_steps(run_input, run_id)


@router.get("/workflows")
def list_workflow_runs(limit: int = Query(default=20, ge=1, le=100), status: str | None = None, user_id: str | None = None):
    with session_scope() as s:
        run_repo = WorkflowRunRepository(s)
        runs = run_repo.list_recent(limit=limit, status=status, user_id=user_id)
        return {"status": "success", "data": [_serialize_run(run) for run in runs]}


@router.get("/workflows/{run_id}")
def get_workflow_run(run_id: str):
    with session_scope() as s:
        run_repo = WorkflowRunRepository(s)
        step_repo = WorkflowStepRunRepository(s)
        cand_repo = CandidateRepository(s)
        watch_repo = WatchlistRepository(s)

        run = run_repo.get(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="workflow run not found")

        return {
            "status": "success",
            "data": {
                "run": _serialize_run(run),
                "steps": [_serialize_step(st) for st in step_repo.list_by_workflow_run(run_id)],
                "candidates": [_serialize_candidate(c) for c in cand_repo.list_by_workflow_run(run_id)],
                "watchlist": [_serialize_watchlist(w) for w in watch_repo.list_by_workflow_run(run_id)],
            },
        }


@router.get("/workflows/{run_id}/steps/{step_code}")
def get_workflow_step(run_id: str, step_code: str):
    with session_scope() as s:
        step_repo = WorkflowStepRunRepository(s)
        steps = step_repo.list_by_workflow_run(run_id)
        step = next((st for st in steps if st.step_code == step_code), None)
        if not step:
            raise HTTPException(status_code=404, detail="workflow step not found")
        return {"status": "success", "data": _serialize_step(step)}


@router.get("/workflows/{run_id}/candidates")
def get_workflow_candidates(run_id: str, status: str | None = None):
    with session_scope() as s:
        cand_repo = CandidateRepository(s)
        rows = cand_repo.list_by_status(run_id, status) if status else cand_repo.list_by_workflow_run(run_id)
        return {"status": "success", "data": [_serialize_candidate(c) for c in rows]}


@router.get("/watchlist")
def get_watchlist(view: str = Query(default='all', pattern='^(all|latest)$')):
    with session_scope() as s:
        watch_repo = WatchlistRepository(s)
        rows = watch_repo.list_latest() if view == 'latest' else watch_repo.list_all()
        return {"status": "success", "data": [_serialize_watchlist(w) for w in rows]}


@router.get("/watchlist/latest")
def get_watchlist_latest():
    with session_scope() as s:
        watch_repo = WatchlistRepository(s)
        rows = watch_repo.list_latest()
        return {"status": "success", "data": [_serialize_watchlist(w) for w in rows]}


def _candidate_data_from_watchlist_entry(entry) -> dict[str, Any]:
    def _text_or_num(text_value: Any, num_value: Any) -> Any:
        if text_value is not None and str(text_value).strip() != '':
            return text_value
        return num_value

    return {
        'symbol': entry.symbol,
        'name': entry.name,
        'board': getattr(entry, 'board', '') or '',
        'pe_ttm': _text_or_num(getattr(entry, 'pe_ttm', ''), getattr(entry, 'pe_ttm_num', None)),
        'pb': _text_or_num(getattr(entry, 'pb', ''), getattr(entry, 'pb_num', None)),
        'latest_price': _text_or_num(getattr(entry, 'latest_price', ''), getattr(entry, 'latest_price_num', None)),
        'dividend_yield': _text_or_num(getattr(entry, 'dividend_yield', ''), getattr(entry, 'dividend_yield_num', None)),
        'month_return': _text_or_num(getattr(entry, 'month_return', ''), getattr(entry, 'month_return_num', None)),
        'st_flag': getattr(entry, 'st_flag', '否') or '否',
    }


def _has_complete_risk_inputs(data: dict[str, Any]) -> bool:
    required = ('pb', 'pe_ttm', 'month_return', 'dividend_yield')
    for key in required:
        value = data.get(key)
        if value is None:
            return False
        if isinstance(value, str) and value.strip() == '':
            return False
    return True


def _safe_metric_number(value: Any) -> float | None:
    return _runner().risk_assessor.safe_float(value)


@router.patch("/watchlist/{entry_id}")
def update_watchlist_entry(entry_id: str, payload: WatchlistUpdateRequest):
    with session_scope() as s:
        watch_repo = WatchlistRepository(s)
        entry = watch_repo.get(entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="watchlist entry not found")

        risk_level = None
        if payload.risk_level is not None:
            try:
                risk_level = RiskLevel(payload.risk_level)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid risk_level") from exc

        catalyst_factors = payload.catalyst_factors
        derived_data = _candidate_data_from_watchlist_entry(entry)
        if payload.board is not None:
            derived_data['board'] = payload.board
        if payload.pe_ttm is not None:
            derived_data['pe_ttm'] = payload.pe_ttm
        if payload.pb is not None:
            derived_data['pb'] = payload.pb
        if payload.latest_price is not None:
            derived_data['latest_price'] = payload.latest_price
        if payload.dividend_yield is not None:
            derived_data['dividend_yield'] = payload.dividend_yield
        if payload.month_return is not None:
            derived_data['month_return'] = payload.month_return
        if payload.st_flag is not None:
            derived_data['st_flag'] = payload.st_flag

        should_recompute = _has_complete_risk_inputs(derived_data)

        if catalyst_factors is None:
            catalyst_factors = entry.catalyst_factors

        if risk_level is None:
            risk_level = _runner().risk_assessor.derive_risk_level(derived_data) if should_recompute else entry.risk_level

        entry_reason = payload.entry_reason
        if entry_reason is None:
            entry_reason = _runner().entry_reason_builder.derive_entry_reason(derived_data, catalyst_factors) if should_recompute else entry.entry_reason

        watch_price_zone = payload.watch_price_zone
        if watch_price_zone is None:
            watch_price_zone = _runner().price_zone_builder.derive_watch_price_zone(entry.name, entry.symbol, derived_data) if should_recompute else entry.watch_price_zone

        updated = watch_repo.update(
            entry,
            entry_reason=entry_reason,
            risk_level=risk_level,
            catalyst_factors=catalyst_factors,
            watch_price_zone=watch_price_zone,
            board=payload.board,
            pe_ttm=payload.pe_ttm,
            pe_ttm_num=_safe_metric_number(payload.pe_ttm) if payload.pe_ttm is not None else None,
            pb=payload.pb,
            pb_num=_safe_metric_number(payload.pb) if payload.pb is not None else None,
            latest_price=payload.latest_price,
            latest_price_num=_safe_metric_number(payload.latest_price) if payload.latest_price is not None else None,
            dividend_yield=payload.dividend_yield,
            dividend_yield_num=_safe_metric_number(payload.dividend_yield) if payload.dividend_yield is not None else None,
            month_return=payload.month_return,
            month_return_num=_safe_metric_number(payload.month_return) if payload.month_return is not None else None,
            st_flag=payload.st_flag,
        )
        return {"status": "success", "data": _serialize_watchlist(updated)}

@router.delete("/watchlist/{entry_id}")
def delete_watchlist_entry(entry_id: str):
    with session_scope() as s:
        watch_repo = WatchlistRepository(s)
        entry = watch_repo.get(entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="watchlist entry not found")
        watch_repo.delete(entry)
        return {"status": "success", "deleted": 1}


@router.post("/watchlist/batch-delete")
def batch_delete_watchlist(payload: dict):
    entry_ids = payload.get("ids", [])
    if not entry_ids:
        raise HTTPException(status_code=400, detail="ids is required")
    with session_scope() as s:
        watch_repo = WatchlistRepository(s)
        deleted = watch_repo.delete_by_ids(entry_ids)
        return {"status": "success", "deleted": deleted}
