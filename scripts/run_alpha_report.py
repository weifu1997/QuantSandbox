from __future__ import annotations

from pathlib import Path
import sys
import argparse
import json
from dataclasses import asdict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.api.config_endpoints import get_data_center
from backend.research.dataset_builder import build_alpha_dataset
from backend.research.factor_analysis import analyze_factor_ic
from backend.research.factor_library import get_research_factor_library
from backend.research.group_backtest import run_group_backtest
from backend.research.report_builder import build_alpha_report
from backend.research.topn_backtest import run_topn_backtest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run alpha research report from CLI.')
    parser.add_argument('--factor', required=True)
    parser.add_argument('--horizon', type=int, required=True)
    parser.add_argument('--start-date', default='20240101')
    parser.add_argument('--end-date', default='')
    parser.add_argument('--tickers', default='sh600519,sz000858')
    parser.add_argument('--groups', type=int, default=5)
    parser.add_argument('--top-n', type=int, default=5)
    parser.add_argument('--rebalance-frequency', default='W')
    parser.add_argument('--transaction-cost-bps', type=float, default=10.0)
    parser.add_argument('--benchmark', default='equal_weight_universe')
    parser.add_argument('--weighting', default='equal')
    parser.add_argument('--output-format', choices=['json', 'markdown'], default='json')
    parser.add_argument('--min-cross-section', type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dc = get_data_center()
    latest_trade_date = dc.get_latest_trade_date()
    end_date = args.end_date or latest_trade_date
    tickers = [item.strip() for item in args.tickers.split(',') if item.strip()]
    horizons = [args.horizon]
    factor_library = get_research_factor_library()

    dataset = build_alpha_dataset(
        tickers=tickers,
        start_date=args.start_date,
        end_date=end_date,
        factors=[args.factor],
        horizons=horizons,
        data_center=dc,
        factor_registry=factor_library,
    )
    factor_report = analyze_factor_ic(
        dataset=dataset,
        factor_name=args.factor,
        horizons=horizons,
        min_cross_section=args.min_cross_section,
        factor_library=factor_library,
    )
    group_report = run_group_backtest(
        dataset=dataset,
        factor_name=args.factor,
        horizon=args.horizon,
        groups=args.groups,
        rebalance_frequency=args.rebalance_frequency,
        factor_library=factor_library,
    )
    topn_report = run_topn_backtest(
        dataset=dataset,
        factor_name=args.factor,
        horizon=args.horizon,
        top_n=args.top_n,
        rebalance_frequency=args.rebalance_frequency,
        weighting=args.weighting,
        transaction_cost_bps=args.transaction_cost_bps,
        benchmark=args.benchmark,
    )
    report = build_alpha_report(
        config={
            'ticker_count': len(tickers),
            'start_date': args.start_date,
            'end_date': end_date,
            'factors': [args.factor],
            'horizons': horizons,
            'groups': args.groups,
            'top_n': args.top_n,
            'rebalance_frequency': args.rebalance_frequency,
            'transaction_cost_bps': args.transaction_cost_bps,
            'weighting': args.weighting,
            'benchmark': args.benchmark,
        },
        dataset_summary={
            'rows': int(len(dataset)),
            'tickers': tickers,
            'factors': [args.factor],
            'horizons': horizons,
            'valid_sample_ratio': float(dataset['is_valid_sample'].mean()) if 'is_valid_sample' in dataset.columns and not dataset.empty else 0.0,
            'invalid_reasons': {},
        },
        factor_reports={args.factor: factor_report},
        group_reports={args.factor: group_report},
        topn_reports={args.factor: topn_report},
        output_format=args.output_format,
    )
    if args.output_format == 'markdown':
        print(report.markdown)
    else:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
