from backend.services.mx.xuangu_service import XuanguService
from backend.workflows.low_value_flow.runner import LowValueWorkflowRunner


class _StubDataCenter:
    def __init__(self):
        self.calls = []

    def _to_ts_code(self, symbol: str) -> str:
        return '603166.SH'

    def get_latest_trade_date(self) -> str:
        return '20260509'

    def fetch_stock_data(self, symbol: str, start_date: str, end_date: str):
        import pandas as pd
        self.calls.append(('fetch_stock_data', symbol, start_date, end_date))
        rows = []
        for i in range(25):
            rows.append({'date': f'2026-04-{i+1:02d}', 'close': 10 + i * 0.1})
        rows.append({'date': '2026-05-08', 'close': 14.60})
        return pd.DataFrame(rows)

    def _tushare_post(self, api_name: str, params: dict, fields: str | None = None):
        self.calls.append((api_name, params, fields))
        if api_name == 'stock_basic':
            return {'data': {'items': [['603166.SH', '福达股份', '主板', '20141127']]}}
        if api_name == 'daily_basic':
            return {'data': {'items': [['603166.SH', '20260508', 3.4481, 29.7751, 28.8637, 0.6754, 0.6754]]}}
        raise AssertionError(api_name)


def test_xuangu_parse_enriches_board_and_dividend_yield_from_tushare_when_source_missing():
    service = XuanguService()
    service.data_center = _StubDataCenter()
    raw = {
        'csv_path': '',
        'description_path': '',
        'raw_json': {
            'data': {
                'data': {
                    'allResults': {
                        'result': {
                            'dataList': [
                                {
                                    'SECURITY_CODE': '603166',
                                    'SECURITY_SHORT_NAME': '福达股份',
                                    'NEWEST_PRICE': '14.60',
                                    '010000_PB<70>{2026-05-08}': '3.6164',
                                    '010000_PE_D{2026-05-08}': '31.38',
                                }
                            ]
                        }
                    }
                }
            }
        },
    }
    parsed = service._parse(raw)
    row = parsed['candidates'][0]
    assert row['board'] == '主板'
    assert row['dividend_yield'] == '0.6754'
    assert row['month_return'] == '39.05'


def test_xuangu_parse_prefers_dynamic_and_plain_csv_columns(tmp_path):
    csv_path = tmp_path / 'xuangu.csv'
    csv_path.write_text(
        '代码,名称,上市板块,最新价(元),市盈率(TTM)(倍),市净率(倍),年度股息率(%),区间涨跌幅(%)\n'
        '603166,福达股份,主板,14.60,31.38,3.6164,0.6754,7.83\n',
        encoding='utf-8-sig',
    )
    service = XuanguService()
    service.data_center = _StubDataCenter()
    parsed = service._parse({'csv_path': str(csv_path), 'description_path': '', 'raw_json': {}})
    row = parsed['candidates'][0]
    assert row['board'] == '主板'
    assert row['latest_price'] == '14.60'
    assert row['pe_ttm'] == '31.38'
    assert row['pb'] == '3.6164'
    assert row['dividend_yield'] == '0.6754'
    assert row['month_return'] == '7.83'


def test_watch_price_zone_uses_candidate_latest_price_when_snapshot_missing():
    runner = LowValueWorkflowRunner()
    runner.price_zone_builder.extract_latest_snapshot = lambda sec_name, symbol: None
    zone = runner.price_zone_builder.derive_watch_price_zone(
        '福达股份',
        '603166',
        {
            'pb': '3.6164',
            'latest_price': '14.60',
        },
    )
    assert zone == '4.04~5.25 元（PB 1.0~1.3）'


def test_watchlist_recompute_needs_persisted_base_factors():
    runner = LowValueWorkflowRunner()
    candidate_data = {
        'symbol': '603166',
        'name': '福达股份',
        'board': '主板',
        'pb': '3.6164',
        'pe_ttm': '31.38',
        'latest_price': '14.60',
        'dividend_yield': '0.6754',
        'month_return': '13.00',
        'st_flag': '否',
    }
    reason = runner.entry_reason_builder.derive_entry_reason(candidate_data, ['分红催化'])
    assert reason == 'PB 3.62；PE 31.38；股息率 0.68%；近20交易日 13.00%；催化: 分红催化'
