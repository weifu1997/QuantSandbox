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
from backend.research.factor_library import get_research_factor_library
from backend.research.topn_backtest import run_topn_backtest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run alpha TopN backtest from CLI.')
    parser.add_argument('--factor', required=True)
    parser.add_argument('--top-n', type=int, required=True)
    parser.add_argument('--horizon', type=int, default=20)
    parser.add_argument('--start-date', default='20240101')
    parser.add_argument('--end-date', default='')
    parser.add_argument('--tickers', default='sh600519,sz000858')
    parser.add_argument('--rebalance-frequency', default='W')
    parser.add_argument('--weighting', default='equal')
    parser.add_argument('--transaction-cost-bps', type=float, default=10.0)
    parser.add_argument('--benchmark', default='equal_weight_universe')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dc = get_data_center()
    latest_trade_date = dc.get_latest_trade_date()
    end_date = args.end_date or latest_trade_date
    tickers = [item.strip() for item in args.tickers.split(',') if item.strip()]

    dataset = build_alpha_dataset(
        tickers=tickers,
        start_date=args.start_date,
        end_date=end_date,
        factors=[args.factor],
        horizons=[args.horizon],
        data_center=dc,
        factor_registry=get_research_factor_library(),
    )
    report = run_topn_backtest(
        dataset=dataset,
        factor_name=args.factor,
        horizon=args.horizon,
        top_n=args.top_n,
        rebalance_frequency=args.rebalance_frequency,
        weighting=args.weighting,
        transaction_cost_bps=args.transaction_cost_bps,
        benchmark=args.benchmark,
    )
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
