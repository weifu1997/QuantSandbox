from __future__ import annotations

from pathlib import Path
import sys
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
from backend.research.topn_backtest import run_topn_backtest


def main() -> None:
    factors = ['momentum_20d']
    horizons = [20]
    tickers = ['sh600519', 'sz000858']
    dc = get_data_center()
    latest_trade_date = dc.get_latest_trade_date()

    dataset = build_alpha_dataset(
        tickers=tickers,
        start_date='20240101',
        end_date=latest_trade_date,
        factors=factors,
        horizons=horizons,
        data_center=dc,
        factor_registry=get_research_factor_library(),
    )
    factor_report = analyze_factor_ic(
        dataset=dataset,
        factor_name='momentum_20d',
        horizons=horizons,
        min_cross_section=2,
        factor_library=get_research_factor_library(),
    )
    group_report = run_group_backtest(
        dataset=dataset,
        factor_name='momentum_20d',
        horizon=20,
        groups=2,
        rebalance_frequency='W',
        factor_library=get_research_factor_library(),
    )
    topn_report = run_topn_backtest(
        dataset=dataset,
        factor_name='momentum_20d',
        horizon=20,
        top_n=1,
        rebalance_frequency='W',
        weighting='equal',
        transaction_cost_bps=10,
        benchmark='equal_weight_universe',
    )

    payload = {
        'status': 'success',
        'tickers': tickers,
        'latest_trade_date': latest_trade_date,
        'dataset_rows': int(len(dataset)),
        'factor_ic': {
            'factor_name': factor_report.factor_name,
            'horizons': {str(k): asdict(v) for k, v in factor_report.horizons.items()},
        },
        'group_backtest': {
            'long_short_return': group_report.long_short_return,
            'monotonicity_score': group_report.monotonicity_score,
            'group_return_by_group': group_report.group_return_by_group,
        },
        'topn_backtest': {
            'total_return': topn_report.total_return,
            'annual_return': topn_report.annual_return,
            'excess_return_vs_equal_weight': topn_report.excess_return_vs_equal_weight,
            'holdings_keys': list(topn_report.holdings_by_rebalance_date.keys())[:5],
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
