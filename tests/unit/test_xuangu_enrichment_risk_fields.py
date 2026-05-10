from __future__ import annotations

from backend.services.mx.xuangu_service import XuanguService


class DummyDataCenter:
    def _to_ts_code(self, symbol: str) -> str:
        return symbol + '.SZ'

    def _tushare_post(self, api_name: str, params: dict, fields: str | None = None) -> dict:
        if api_name == 'stock_basic':
            return {'data': {'items': [['003012.SZ', '东鹏控股', '深交所主板', '20201019']]}}
        if api_name == 'daily_basic':
            return {'data': {'items': [['003012.SZ', '20260508', None, None, None, '3.21', '3.82']]}}
        if api_name == 'fina_indicator':
            return {
                'data': {
                    'fields': ['ts_code', 'end_date', 'q_sales_yoy', 'sales_yoy', 'q_dtprofit_yoy', 'dt_netprofit_yoy', 'current_ratio', 'quick_ratio', 'audit_result'],
                    'items': [
                        ['003012.SZ', '20250331', '12.5', '10.0', '8.6', '7.2', '1.45', '1.10', '标准意见'],
                        ['003012.SZ', '20241231', '9.5', '8.0', '6.6', '5.2', '1.35', '1.00', '标准意见'],
                    ],
                }
            }
        raise AssertionError(api_name)

    def get_latest_trade_date(self) -> str:
        return '20260508'

    def fetch_stock_data(self, symbol: str, start_date: str, end_date: str):
        raise AssertionError('should not be called')


def test_fetch_candidate_enrichment_includes_risk_fields():
    service = XuanguService()
    service.data_center = DummyDataCenter()

    result = service._fetch_candidate_enrichment('003012', trade_date_hint='20260508')

    assert result['board'] == '深交所主板'
    assert result['dividend_yield'] == '3.82'
    assert result['revenue_yoy'] == '12.5'
    assert result['revenue_growth'] == '9.5'
    assert result['profit_yoy'] == '8.6'
    assert result['net_profit_change'] == '6.6'
    assert result['current_ratio'] == '1.45'
    assert result['quick_ratio'] == '1.10'
    assert result['audit_opinion'] == '标准意见'
    assert result['risk_flags'] == []


def test_parse_merges_enrichment_fields_into_candidates(monkeypatch, tmp_path):
    csv_path = tmp_path / 'xuangu.csv'
    csv_path.write_text('代码,名称,市净率(倍),市盈率(动)(倍),最新价(元),区间涨跌幅(%),ST股票\n003012,东鹏控股,0.8658,19.70,5.66,-11.15,否\n', encoding='utf-8-sig')

    service = XuanguService()
    monkeypatch.setattr(service, '_fetch_candidate_enrichment', lambda symbol, trade_date_hint='': {
        'board': '深交所主板',
        'dividend_yield': '3.82',
        'revenue_yoy': '12.5',
        'revenue_growth': '9.5',
        'profit_yoy': '8.6',
        'net_profit_change': '6.6',
        'current_ratio': '1.45',
        'quick_ratio': '1.10',
        'audit_opinion': '标准意见',
        'regulatory_inquiry': '',
        'risk_flags': [],
    })
    monkeypatch.setattr(service, '_extract_trade_date_hint', lambda raw: '20260508')

    parsed = service._parse({'csv_path': str(csv_path), 'description_path': ''})
    candidate = parsed['candidates'][0]

    assert candidate['symbol'] == '003012'
    assert candidate['board'] == '深交所主板'
    assert candidate['dividend_yield'] == '3.82'
    assert candidate['revenue_yoy'] == '12.5'
    assert candidate['current_ratio'] == '1.45'
    assert candidate['audit_opinion'] == '标准意见'
    assert candidate['risk_flags'] == []
