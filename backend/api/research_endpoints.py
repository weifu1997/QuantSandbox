from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.api.config_endpoints import get_data_center
from backend.research.dataset_builder import build_alpha_dataset
from backend.research.factor_analysis import analyze_factor_ic
from backend.research.factor_library import get_research_factor_library
from backend.research.group_backtest import run_group_backtest
from backend.research.report_builder import build_alpha_report
from backend.research.topn_backtest import run_topn_backtest

router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchDatasetBuildRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    start_date: str
    end_date: str
    factors: list[str] = Field(default_factory=list)
    horizons: list[int] = Field(default_factory=lambda: [5, 20, 60])
    price_adjust: str = "qfq"


class ResearchFactorICRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    start_date: str
    end_date: str
    factor_name: str
    horizons: list[int] = Field(default_factory=lambda: [5, 20, 60])
    min_cross_section: int = 10


class ResearchGroupBacktestRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    start_date: str
    end_date: str
    factor_name: str
    horizon: int = 20
    groups: int = 5
    rebalance_frequency: str = "D"


class ResearchTopNBacktestRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    start_date: str
    end_date: str
    factor_name: str
    horizon: int = 20
    top_n: int = 10
    rebalance_frequency: str = "W"
    weighting: str = "equal"
    transaction_cost_bps: float = 10.0
    benchmark: str = "equal_weight_universe"


class ResearchReportRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    start_date: str
    end_date: str
    factors: list[str] = Field(default_factory=list)
    horizons: list[int] = Field(default_factory=lambda: [20])
    min_cross_section: int = 10
    groups: int = 5
    rebalance_frequency: str = "W"
    top_n: int = 10
    weighting: str = "equal"
    transaction_cost_bps: float = 10.0
    benchmark: str = "equal_weight_universe"
    output_format: str = "json"


def _dataset_summary(df, tickers: list[str], factors: list[str], horizons: list[int]) -> dict[str, Any]:
    invalid = {}
    if not df.empty and "missing_reason" in df.columns:
        counts = df.loc[df.get("is_valid_sample") == False, "missing_reason"].value_counts(dropna=True)
        invalid = {str(k): int(v) for k, v in counts.items()}
    valid_ratio = float(df["is_valid_sample"].mean()) if (not df.empty and "is_valid_sample" in df.columns) else 0.0
    return {
        "rows": int(len(df)),
        "tickers": tickers,
        "factors": factors,
        "horizons": horizons,
        "valid_sample_ratio": valid_ratio,
        "invalid_reasons": invalid,
    }


def _serialize_factor_ic_report(report) -> dict[str, Any]:
    return {
        "factor_name": report.factor_name,
        "horizons": {
            str(h): {
                "horizon": stats.horizon,
                "ic_mean": stats.ic_mean,
                "ic_std": stats.ic_std,
                "ic_ir": stats.ic_ir,
                "rank_ic_mean": stats.rank_ic_mean,
                "rank_ic_std": stats.rank_ic_std,
                "rank_ic_ir": stats.rank_ic_ir,
                "positive_ic_ratio": stats.positive_ic_ratio,
                "sample_count": stats.sample_count,
                "missing_ratio": stats.missing_ratio,
                "monthly_ic_series": stats.monthly_ic_series,
            }
            for h, stats in report.horizons.items()
        },
        "warnings": report.warnings,
    }


def _build_dataset(payload_tickers: list[str], start_date: str, end_date: str, factors: list[str], horizons: list[int]):
    return build_alpha_dataset(
        tickers=payload_tickers,
        start_date=start_date,
        end_date=end_date,
        factors=factors,
        horizons=horizons,
        data_center=get_data_center(),
        factor_registry=get_research_factor_library(),
    )


@router.post("/dataset/build")
def research_dataset_build(payload: ResearchDatasetBuildRequest):
    df = _build_dataset(payload.tickers, payload.start_date, payload.end_date, payload.factors, payload.horizons)
    return {
        "status": "success",
        "data": _dataset_summary(df, payload.tickers, payload.factors, payload.horizons),
    }


@router.post("/factor/ic")
def research_factor_ic(payload: ResearchFactorICRequest):
    df = _build_dataset(payload.tickers, payload.start_date, payload.end_date, [payload.factor_name], payload.horizons)
    report = analyze_factor_ic(
        dataset=df,
        factor_name=payload.factor_name,
        horizons=payload.horizons,
        min_cross_section=payload.min_cross_section,
        factor_library=get_research_factor_library(),
    )
    return {
        "status": "success",
        "data": _serialize_factor_ic_report(report),
    }


@router.post("/factor/group-backtest")
def research_factor_group_backtest(payload: ResearchGroupBacktestRequest):
    df = _build_dataset(payload.tickers, payload.start_date, payload.end_date, [payload.factor_name], [payload.horizon])
    report = run_group_backtest(
        dataset=df,
        factor_name=payload.factor_name,
        horizon=payload.horizon,
        groups=payload.groups,
        rebalance_frequency=payload.rebalance_frequency,
    )
    return {
        "status": "success",
        "data": asdict(report),
    }


@router.post("/topn-backtest")
def research_topn_backtest(payload: ResearchTopNBacktestRequest):
    df = _build_dataset(payload.tickers, payload.start_date, payload.end_date, [payload.factor_name], [payload.horizon])
    report = run_topn_backtest(
        dataset=df,
        factor_name=payload.factor_name,
        horizon=payload.horizon,
        top_n=payload.top_n,
        rebalance_frequency=payload.rebalance_frequency,
        weighting=payload.weighting,
        transaction_cost_bps=payload.transaction_cost_bps,
        benchmark=payload.benchmark,
    )
    return {
        "status": "success",
        "data": asdict(report),
    }


@router.post("/report")
def research_report(payload: ResearchReportRequest):
    if not payload.factors:
        raise ValueError("factors must not be empty")
    if not payload.horizons:
        raise ValueError("horizons must not be empty")

    horizon = int(payload.horizons[0])
    df = _build_dataset(payload.tickers, payload.start_date, payload.end_date, payload.factors, payload.horizons)
    dataset_summary = _dataset_summary(df, payload.tickers, payload.factors, payload.horizons)

    factor_reports = {}
    group_reports = {}
    topn_reports = {}
    for factor_name in payload.factors:
        factor_reports[factor_name] = analyze_factor_ic(
            dataset=df,
            factor_name=factor_name,
            horizons=payload.horizons,
            min_cross_section=payload.min_cross_section,
            factor_library=get_research_factor_library(),
        )
        group_reports[factor_name] = run_group_backtest(
            dataset=df,
            factor_name=factor_name,
            horizon=horizon,
            groups=payload.groups,
            rebalance_frequency=payload.rebalance_frequency,
            factor_library=get_research_factor_library(),
        )
        topn_reports[factor_name] = run_topn_backtest(
            dataset=df,
            factor_name=factor_name,
            horizon=horizon,
            top_n=payload.top_n,
            rebalance_frequency=payload.rebalance_frequency,
            weighting=payload.weighting,
            transaction_cost_bps=payload.transaction_cost_bps,
            benchmark=payload.benchmark,
        )

    report = build_alpha_report(
        config={
            "ticker_count": len(payload.tickers),
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "factors": payload.factors,
            "horizons": payload.horizons,
            "groups": payload.groups,
            "top_n": payload.top_n,
            "rebalance_frequency": payload.rebalance_frequency,
            "transaction_cost_bps": payload.transaction_cost_bps,
            "weighting": payload.weighting,
            "benchmark": payload.benchmark,
        },
        dataset_summary=dataset_summary,
        factor_reports=factor_reports,
        group_reports=group_reports,
        topn_reports=topn_reports,
        output_format=payload.output_format,
    )

    data = asdict(report)
    if payload.output_format.lower() == "markdown":
        data = {
            "title": report.title,
            "generated_at": report.generated_at,
            "output_format": report.output_format,
            "markdown": report.markdown,
            "config": report.config,
            "dataset": report.dataset,
            "conclusion": asdict(report.conclusion),
        }
    return {
        "status": "success",
        "data": data,
    }
