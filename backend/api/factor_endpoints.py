from __future__ import annotations

from fastapi import APIRouter

from backend.core.factors import get_factor_registry

router = APIRouter(prefix="/api", tags=["factors"])


@router.get("/factors", summary="列出可用因子")
def list_factors():
    registry = get_factor_registry()
    return {
        "status": "success",
        "factors": registry.list_meta(),
    }
