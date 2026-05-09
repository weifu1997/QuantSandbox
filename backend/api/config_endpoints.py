from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import yaml
from fastapi import APIRouter
from pydantic import BaseModel

from backend.core.data_center import DataCenter

router = APIRouter(prefix="/api", tags=["config"])
dc = DataCenter()


class ConfigUpdateRequest(BaseModel):
    stock_pool: list[str] | None = None
    strategy_name: str | None = None
    strategy_parameters: dict | None = None


def load_config() -> dict:
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../config.yaml"))
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config: dict) -> None:
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../config.yaml"))
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="config_", suffix=".yaml", dir=os.path.dirname(config_path))
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
        os.replace(tmp_path, config_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def clean_nan(df: pd.DataFrame) -> list:
    return df.fillna("").to_dict(orient="records")


@router.get("/config", summary="获取回测配置")
def get_config():
    config = load_config()
    return {
        "status": "success",
        "stock_pool": config.get("stock_pool", []),
        "strategy": config.get("strategy", {}),
    }


@router.post("/config", summary="更新回测配置")
def update_config(payload: ConfigUpdateRequest):
    config = load_config()
    if payload.stock_pool is not None:
        config["stock_pool"] = payload.stock_pool
    if payload.strategy_name is not None:
        config.setdefault("strategy", {})["name"] = payload.strategy_name
    if payload.strategy_parameters is not None:
        config.setdefault("strategy", {})["parameters"] = payload.strategy_parameters
    save_config(config)
    return {"status": "success"}


@router.get("/meta", summary="获取系统元信息")
def get_meta():
    latest_trade_date = dc.get_latest_trade_date()
    return {
        "status": "success",
        "latest_trade_date": latest_trade_date,
        "data_sources": dc.get_source_status(),
        "priority": dc.get_source_priority(),
    }
