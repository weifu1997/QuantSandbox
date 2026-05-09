from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.schemas import MXQueryRequest
from backend.services.mx import DataService, SearchService, XuanguService
from backend.services.mx.zixuan_service import MoniService

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
def mx_data(payload: MXQueryRequest):
    result = DataService().run(payload.query, timeout=120)
    return _mx_response(result)


@router.post("/search", summary="妙想资讯搜索")
def mx_search(payload: MXQueryRequest):
    result = SearchService().run(payload.query, timeout=120)
    return _mx_response(result)


@router.post("/xuangu", summary="妙想智能选股")
def mx_xuangu(payload: MXQueryRequest):
    result = XuanguService().run(payload.query, timeout=180)
    return _mx_response(result)


@router.post("/moni", summary="妙想模拟组合查询")
def mx_moni(payload: MXQueryRequest):
    result = MoniService().run(payload.query, timeout=120)
    return _mx_response(result)
