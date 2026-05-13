from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from backend.research.schemas import (
    AlphaResearchConclusion,
    AlphaResearchFactorSummary,
    AlphaResearchReport,
    FactorICReport,
    GroupBacktestReport,
    TopNBacktestReport,
)


def _determine_verdict(
    rank_ic_mean: float,
    ic_ir: float,
    long_short_return: float,
    excess_return: float,
) -> str:
    if rank_ic_mean > 0.03 and ic_ir > 0.3 and long_short_return > 0.05 and excess_return > 0:
        return "recommended"
    if rank_ic_mean <= 0 or long_short_return <= 0 or excess_return <= 0:
        return "rejected"
    return "watchlist"


def _factor_notes(
    *,
    rank_ic_mean: float,
    ic_ir: float,
    long_short_return: float,
    monotonicity_score: float,
    excess_return: float,
) -> list[str]:
    notes: list[str] = []
    if rank_ic_mean > 0.03:
        notes.append("RankIC 均值超过 0.03。")
    else:
        notes.append("RankIC 均值未达到 0.03。")

    if ic_ir > 0.3:
        notes.append("ICIR 超过 0.3。")
    else:
        notes.append("ICIR 未达到 0.3。")

    if long_short_return > 0.05:
        notes.append("Q5-Q1 多空收益超过 5%。")
    else:
        notes.append("Q5-Q1 多空收益未达到 5%。")

    if monotonicity_score >= 0.75:
        notes.append("分组收益具备较好单调性。")
    else:
        notes.append("分组收益单调性一般，需要人工复核。")

    if excess_return > 0:
        notes.append("TopN 成本后跑赢等权基准。")
    else:
        notes.append("TopN 成本后未跑赢等权基准。")
    return notes


def _build_conclusion(summaries: list[AlphaResearchFactorSummary]) -> AlphaResearchConclusion:
    recommended = [item.factor_name for item in summaries if item.verdict == "recommended"]
    rejected = [item.factor_name for item in summaries if item.verdict == "rejected"]
    watchlist = [item.factor_name for item in summaries if item.verdict == "watchlist"]

    summary_lines = [
        f"推荐因子 {len(recommended)} 个，弃用因子 {len(rejected)} 个，待进一步验证因子 {len(watchlist)} 个。"
    ]
    if recommended:
        summary_lines.append(f"优先进入策略层验证：{', '.join(recommended)}")
    if rejected:
        summary_lines.append(f"当前建议弃用：{', '.join(rejected)}")
    if watchlist:
        summary_lines.append(f"建议继续样本外验证：{', '.join(watchlist)}")

    return AlphaResearchConclusion(
        recommended_factors=recommended,
        rejected_factors=rejected,
        watchlist_factors=watchlist,
        summary=summary_lines,
    )


def _render_markdown(report: AlphaResearchReport) -> str:
    config = report.config
    dataset = report.dataset
    topn = report.topn_strategy
    lines = [
        f"# {report.title}",
        "",
        f"- 生成时间: {report.generated_at}",
        f"- 股票池数量: {config.get('ticker_count', 0)}",
        f"- 起止日期: {config.get('start_date', '')} ~ {config.get('end_date', '')}",
        f"- 因子列表: {', '.join(config.get('factors', []))}",
        f"- horizons: {', '.join(str(x) for x in config.get('horizons', []))}",
        f"- TopN: {config.get('top_n')} / 分组数: {config.get('groups')} / 调仓频率: {config.get('rebalance_frequency')}",
        f"- 成本假设: {config.get('transaction_cost_bps', 0)} bps",
        "",
        "## 数据集概览",
        "",
        f"- 样本行数: {dataset.get('rows', 0)}",
        f"- 有效样本占比: {dataset.get('valid_sample_ratio', 0.0):.2%}",
        f"- 无效原因: {dataset.get('invalid_reasons', {})}",
        "",
        "## 因子总览表",
        "",
        "| Factor | Horizon | IC | RankIC | ICIR | Missing | Q5-Q1 | Verdict |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in report.factor_summaries:
        lines.append(
            f"| {item.factor_name} | {item.horizon} | {item.ic_mean:.4f} | {item.rank_ic_mean:.4f} | {item.ic_ir:.4f} | {item.missing_ratio:.2%} | {item.group_long_short_return:.2%} | {item.verdict} |"
        )

    lines.extend([
        "",
        "## 单因子详情",
        "",
    ])
    for factor_name, detail in report.factor_details.items():
        lines.append(f"### {factor_name}")
        ic = detail.get("ic", {})
        group = detail.get("group_backtest", {})
        lines.append(f"- 月度 IC: {ic.get('monthly_ic_series', {})}")
        lines.append(f"- Q1~Q5 收益: {group.get('group_return_by_group', {})}")
        lines.append(f"- 多空净值(Q5-Q1): {group.get('long_short_return', 0.0):.2%}")
        lines.append("")

    lines.extend([
        "## TopN 策略",
        "",
        f"- 总收益: {topn.get('total_return', 0.0):.2%}",
        f"- 年化收益: {topn.get('annual_return', 0.0):.2%}",
        f"- 最大回撤: {topn.get('max_drawdown', 0.0):.2%}",
        f"- Sharpe: {topn.get('sharpe', 0.0):.4f}",
        f"- Turnover: {topn.get('turnover', 0.0):.2%}",
        f"- 成本后超额(等权): {topn.get('excess_return_vs_equal_weight', 0.0):.2%}",
        "",
        "## 结论",
        "",
    ])
    lines.extend([f"- {line}" for line in report.conclusion.summary])
    return "\n".join(lines)


def build_alpha_report(
    *,
    config: dict[str, Any],
    dataset_summary: dict[str, Any],
    factor_reports: dict[str, FactorICReport],
    group_reports: dict[str, GroupBacktestReport],
    topn_reports: dict[str, TopNBacktestReport],
    output_format: str = "json",
) -> AlphaResearchReport:
    normalized_format = output_format.lower()
    if normalized_format not in {"json", "markdown"}:
        raise ValueError(f"unsupported output_format: {output_format}")

    factor_summaries: list[AlphaResearchFactorSummary] = []
    factor_details: dict[str, dict[str, Any]] = {}

    for factor_name in config.get("factors", []):
        ic_report = factor_reports[factor_name]
        group_report = group_reports[factor_name]
        topn_report = topn_reports[factor_name]
        horizon = int(config.get("horizons", [config.get("horizon", 20)])[0])
        ic_stats = ic_report.horizons[horizon]

        verdict = _determine_verdict(
            rank_ic_mean=ic_stats.rank_ic_mean,
            ic_ir=ic_stats.ic_ir,
            long_short_return=group_report.long_short_return,
            excess_return=topn_report.excess_return_vs_equal_weight,
        )
        notes = _factor_notes(
            rank_ic_mean=ic_stats.rank_ic_mean,
            ic_ir=ic_stats.ic_ir,
            long_short_return=group_report.long_short_return,
            monotonicity_score=group_report.monotonicity_score,
            excess_return=topn_report.excess_return_vs_equal_weight,
        )
        factor_summaries.append(
            AlphaResearchFactorSummary(
                factor_name=factor_name,
                horizon=horizon,
                ic_mean=ic_stats.ic_mean,
                rank_ic_mean=ic_stats.rank_ic_mean,
                ic_ir=ic_stats.ic_ir,
                positive_ic_ratio=ic_stats.positive_ic_ratio,
                missing_ratio=ic_stats.missing_ratio,
                sample_count=ic_stats.sample_count,
                group_long_short_return=group_report.long_short_return,
                group_monotonicity_score=group_report.monotonicity_score,
                topn_total_return=topn_report.total_return,
                topn_annual_return=topn_report.annual_return,
                topn_max_drawdown=topn_report.max_drawdown,
                topn_sharpe=topn_report.sharpe,
                topn_turnover=topn_report.turnover,
                topn_cost_paid=topn_report.cost_paid,
                topn_excess_return_vs_equal_weight=topn_report.excess_return_vs_equal_weight,
                topn_excess_return_vs_benchmark=topn_report.excess_return_vs_benchmark,
                verdict=verdict,
                notes=notes,
            )
        )
        factor_details[factor_name] = {
            "ic": asdict(ic_stats),
            "group_backtest": asdict(group_report),
            "topn_backtest": asdict(topn_report),
            "warnings": list(dict.fromkeys(ic_report.warnings + group_report.warnings + topn_report.warnings)),
        }

    conclusion = _build_conclusion(factor_summaries)
    best_factor = max(
        factor_summaries,
        key=lambda item: (item.rank_ic_mean, item.group_long_short_return, item.topn_excess_return_vs_equal_weight),
    ) if factor_summaries else None
    topn_strategy = asdict(topn_reports[best_factor.factor_name]) if best_factor else {}

    report = AlphaResearchReport(
        title="Alpha Research Report",
        generated_at=datetime.now(UTC).isoformat(),
        output_format=normalized_format,
        config=config,
        dataset=dataset_summary,
        factor_summaries=factor_summaries,
        factor_details=factor_details,
        topn_strategy=topn_strategy,
        conclusion=conclusion,
    )
    report.markdown = _render_markdown(report)
    return report
