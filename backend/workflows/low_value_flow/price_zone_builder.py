from __future__ import annotations

import logging

from backend.services.mx import DataService
from backend.workflows.low_value_flow.risk_assessor import RiskAssessor

logger = logging.getLogger(__name__)


class PriceZoneBuilder:
    def __init__(self, data_service: DataService | None = None, risk_assessor: RiskAssessor | None = None):
        self.data_service = data_service or DataService()
        self.risk_assessor = risk_assessor or RiskAssessor()

    def extract_latest_snapshot(self, sec_name: str, symbol: str) -> dict[str, float | str] | None:
        query = f"{sec_name or symbol} 最新价 市净率"
        try:
            result = self.data_service.run(query, timeout=120)
            raw = (result.parsed or {}).get('raw_json') if result.ok else None
            data = ((raw or {}).get('data') or {}).get('data', {})
            tables = ((data.get('searchDataResultDTO') or {}).get('dataTableDTOList') or [])
            if not tables:
                return None
            table = tables[0]
            raw_table = table.get('rawTable') or {}
            name_map = table.get('nameMap') or {}
            latest_price = None
            latest_pb = None
            dates = raw_table.get('headName') or []
            for code, values in raw_table.items():
                if code == 'headName' or not values:
                    continue
                label = name_map.get(code, '')
                first = values[0]
                if '收盘价' in label or '最新价' in label:
                    latest_price = self.risk_assessor.safe_float(first)
                if '市净率' in label or label == 'PB' or 'PB' in label:
                    latest_pb = self.risk_assessor.safe_float(first)
            if latest_price is None:
                return None
            return {'price': latest_price, 'pb': latest_pb, 'date': dates[0] if dates else ''}
        except Exception as e:
            logger.warning('fetch latest snapshot failed for %s %s: %s', sec_name, symbol, e)
            return None

    def derive_watch_price_zone(self, sec_name: str, symbol: str, candidate_data: dict | None) -> str:
        data = candidate_data or {}
        month_ret = self.risk_assessor.safe_float(data.get('month_return'))
        div = self.risk_assessor.safe_float(data.get('dividend_yield'))
        snapshot = self.extract_latest_snapshot(sec_name, symbol)

        price = None
        current_pb = None
        support_price = None
        if snapshot:
            price = self.risk_assessor.safe_float(snapshot.get('price'))
            current_pb = self.risk_assessor.safe_float(snapshot.get('pb'))

        if price is None:
            for key in ('latest_price', 'price', 'current_price', 'close_price', 'close'):
                price = self.risk_assessor.safe_float(data.get(key))
                if price is not None:
                    break
        if current_pb is None:
            for key in ('pb', 'pb_ratio', 'current_pb'):
                current_pb = self.risk_assessor.safe_float(data.get(key))
                if current_pb is not None:
                    break
        for key in ('support_price', 'prior_low_price', 'support', 'supportLevel'):
            support_price = self.risk_assessor.safe_float(data.get(key))
            if support_price is not None:
                break

        extra = []
        if month_ret is not None and month_ret <= -10:
            extra.append('回撤较深')
        if div is not None and div >= 3:
            extra.append('高股息')

        if support_price is not None and support_price > 0 and (current_pb is None or current_pb > 1.8):
            low_price = support_price * 0.97
            high_price = support_price * 1.05
            suffix = '（支撑位附近）'
            if extra:
                suffix += '，' + ' / '.join(extra)
            return f"{low_price:.2f}~{high_price:.2f} 元{suffix}"

        if price is not None and current_pb is not None and current_pb > 0:
            low_pb, high_pb = (1.0, 1.3) if current_pb >= 1.0 else (0.8, 1.0)
            low_price = price * low_pb / current_pb
            high_price = price * high_pb / current_pb
            if low_price > high_price:
                low_price, high_price = high_price, low_price
            suffix = f"（PB {low_pb:.1f}~{high_pb:.1f}）"
            if extra:
                suffix += '，' + ' / '.join(extra)
            return f"{low_price:.2f}~{high_price:.2f} 元{suffix}"

        zone_parts: list[str] = []
        if month_ret is not None:
            if month_ret <= -10:
                zone_parts.append('回撤后观察价格区间')
            elif month_ret < 0:
                zone_parts.append('现价附近观察价格区间')
        if div is not None and div >= 3:
            zone_parts.append('高股息支撑')
        if not zone_parts:
            return '现价附近观察价格区间'
        return ' / '.join(zone_parts[:2])
