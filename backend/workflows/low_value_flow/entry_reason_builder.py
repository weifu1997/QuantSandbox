from __future__ import annotations

from backend.workflows.low_value_flow.risk_assessor import RiskAssessor


class EntryReasonBuilder:
    def __init__(self, risk_assessor: RiskAssessor | None = None):
        self.risk_assessor = risk_assessor or RiskAssessor()

    @staticmethod
    def derive_board(symbol: str, explicit_board: str | None = None) -> str:
        board = str(explicit_board or '').strip()
        if board and board not in {'SH', 'SZ'}:
            return board
        code = str(symbol or '').strip().lower()
        if code.startswith(('sh', 'sz')):
            code = code[2:]
        if len(code) >= 2:
            if code.startswith('68'):
                return '科创板'
            if code.startswith('30'):
                return '创业板'
            if code.startswith(('60', '00', '001', '002')):
                return '主板'
            if code.startswith(('4', '8', '92')):
                return '北交所'
        return board

    def derive_entry_reason(self, candidate_data: dict | None, catalysts: list[str]) -> str:
        data = candidate_data or {}
        parts: list[str] = []
        pb = self.risk_assessor.safe_float(data.get('pb'))
        pe = self.risk_assessor.safe_float(data.get('pe_ttm'))
        div = self.risk_assessor.safe_float(data.get('dividend_yield'))
        month_ret = self.risk_assessor.safe_float(data.get('month_return'))
        if pb is not None:
            parts.append(f'PB {pb:.2f}')
        if pe is not None:
            parts.append(f'PE {pe:.2f}')
        if div is not None:
            parts.append(f'股息率 {div:.2f}%')
        if month_ret is not None:
            parts.append(f'近20交易日 {month_ret:.2f}%')
        if catalysts:
            parts.append('催化: ' + ' / '.join(catalysts[:2]))
        return '；'.join(parts) or '低估发现流入池'
