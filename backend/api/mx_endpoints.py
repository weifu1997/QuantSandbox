from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.api.schemas import MXQueryRequest
from backend.services.mx import DataService, SearchService, XuanguService
from backend.services.mx.zixuan_service import MoniService
from backend.services.mx_limiter import run_with_mx_limits
from backend.services.mx.xuangu_async_service import XuanguAsyncService

router = APIRouter(prefix="/api/mx", tags=["mx"])


def _mx_response(result):
    if not result.ok:
        raise HTTPException(status_code=500, detail=result.error_message or f"{result.tool} 执行失败")
    return {
        "status": "success",
        "tool": result.tool,
        "query": result.query,
        "stdout": result.raw.get("stdout", "") if isinstance(result.raw, dict) else "",
        "raw_json": result.raw.get("raw_json") if isinstance(result.raw, dict) else None,
        "warnings": result.warnings,
        **(result.raw if isinstance(result.raw, dict) else {}),
        "parsed": result.parsed,
    }


@router.post("/data", summary="妙想金融数据查询")
def mx_data(payload: MXQueryRequest, request: Request):
    result = run_with_mx_limits(
        'data',
        explicit_user_id=getattr(payload, 'user_id', None),
        client_host=request.client.host if request.client else None,
        func=lambda: DataService().run(payload.query, timeout=120),
    )
    return _mx_response(result)


@router.post("/search", summary="妙想资讯搜索")
def mx_search(payload: MXQueryRequest, request: Request):
    result = run_with_mx_limits(
        'search',
        explicit_user_id=getattr(payload, 'user_id', None),
        client_host=request.client.host if request.client else None,
        func=lambda: SearchService().run(payload.query, timeout=120),
    )
    return _mx_response(result)


@router.post("/xuangu", summary="妙想智能选股（同步兼容接口）")
def mx_xuangu(payload: MXQueryRequest, request: Request):
    result = run_with_mx_limits(
        'xuangu',
        explicit_user_id=getattr(payload, 'user_id', None),
        client_host=request.client.host if request.client else None,
        func=lambda: XuanguService().run(payload.query, timeout=180),
    )
    return _mx_response(result)


@router.post("/xuangu/tasks", summary="妙想智能选股（异步任务）")
def mx_xuangu_task_submit(payload: MXQueryRequest, request: Request):
    result = run_with_mx_limits(
        'xuangu',
        explicit_user_id=getattr(payload, 'user_id', None),
        client_host=request.client.host if request.client else None,
        func=lambda: XuanguAsyncService().submit(payload.query, timeout=180),
    )
    return {"status": "accepted", "data": result}


@router.get("/xuangu/tasks/{task_id}", summary="查询妙想智能选股任务")
def mx_xuangu_task_get(task_id: str):
    data = XuanguAsyncService().get_task_result(task_id)
    if data is None:
        raise HTTPException(status_code=404, detail={"message": f"未找到任务 {task_id}"})
    return {"status": "success", "data": data}


@router.post("/moni", summary="妙想模拟组合查询")
def mx_moni(payload: MXQueryRequest, request: Request):
    result = run_with_mx_limits(
        'moni',
        explicit_user_id=getattr(payload, 'user_id', None),
        client_host=request.client.host if request.client else None,
        func=lambda: MoniService().run(payload.query, timeout=120),
    )
    return _mx_response(result)
