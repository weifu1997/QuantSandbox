from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.services.mx import DataService, SearchService
from backend.services.mx.result import MXServiceResult

AUDIT_BAD_TOKENS = ('保留', '否定', '无法表示')
RISK_KEYWORD_TO_FLAG = {
    '监管警示': '监管警示',
    '监管措施': '监管措施',
    '处罚': '处罚',
    '立案': '立案调查',
    '问询': '监管问询',
    '未及时披露': '信披异常',
    '信披': '信披异常',
    '违规': '违规记录',
}


@dataclass
class RiskEnrichmentResult:
    audit_opinion: str = ''
    regulatory_inquiry: str = ''
    risk_flags: list[str] = field(default_factory=list)
    source_notes: list[str] = field(default_factory=list)
    query: str = ''

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class RiskEnricher:
    def __init__(self, data_service: DataService | None = None, search_service: SearchService | None = None) -> None:
        self.data_service = data_service or DataService()
        self.search_service = search_service or SearchService()

    def enrich(self, candidate: dict[str, Any]) -> RiskEnrichmentResult:
        name = str(candidate.get('name') or '').strip()
        symbol = str(candidate.get('symbol') or '').strip()
        query = self._build_query(name, symbol)
        result = self.data_service.run(query, timeout=180)
        if not result.ok:
            fallback = self._enrich_from_search(name, symbol)
            fallback.query = query
            fallback.source_notes.insert(0, f'mx-data failed: {result.error_message or "unknown"}')
            return fallback

        dto_list = self._extract_tables(result)
        audit_opinion = self._extract_audit_opinion(dto_list)
        regulatory_inquiry = self._extract_regulatory_inquiry(dto_list)
        risk_flags = self._extract_risk_flags(dto_list, audit_opinion, regulatory_inquiry)
        notes = [f'mx-data tables={len(dto_list)}']
        if audit_opinion:
            notes.append('audit from mx-data')
        if regulatory_inquiry:
            notes.append('regulatory summary from mx-data')
        if risk_flags:
            notes.append('risk flags from mx-data')
        if not audit_opinion or not regulatory_inquiry:
            fallback = self._enrich_from_search(name, symbol)
            if fallback.audit_opinion and not audit_opinion:
                audit_opinion = fallback.audit_opinion
                notes.append('audit fallback from mx-search')
            if fallback.regulatory_inquiry and not regulatory_inquiry:
                regulatory_inquiry = fallback.regulatory_inquiry
                notes.append('regulatory fallback from mx-search')
            risk_flags = list(dict.fromkeys(risk_flags + fallback.risk_flags))
            if fallback.risk_flags:
                notes.append('risk flags fallback from mx-search')
        return RiskEnrichmentResult(
            audit_opinion=audit_opinion,
            regulatory_inquiry=regulatory_inquiry,
            risk_flags=risk_flags,
            source_notes=notes,
            query=query,
        )

    @staticmethod
    def _build_query(name: str, symbol: str) -> str:
        label = name or symbol or '该股票'
        if symbol:
            label = f'{label}({symbol})'
        return f'查询 {label} 的审计意见、问询函、立案调查、处罚、监管措施、违规、风险提示'

    @staticmethod
    def _extract_tables(result: MXServiceResult) -> list[dict[str, Any]]:
        raw = result.raw or {}
        raw_json = raw.get('raw_json') or {}
        try:
            return ((((raw_json.get('data') or {}).get('data') or {}).get('searchDataResultDTO') or {}).get('dataTableDTOList') or [])
        except Exception:
            return []

    def _enrich_from_search(self, name: str, symbol: str) -> RiskEnrichmentResult:
        query = self._build_search_query(name, symbol)
        result = self.search_service.run(query, timeout=180)
        if not result.ok:
            return RiskEnrichmentResult(source_notes=[f'mx-search failed: {result.error_message or "unknown"}'], query=query)
        text = self._extract_search_text(result)
        audit_opinion = self._extract_audit_from_search_text(text)
        regulatory_inquiry = self._extract_regulatory_from_search_text(text)
        risk_flags = self._flags_from_text(text)
        notes = ['mx-search fallback used']
        if audit_opinion:
            notes.append('audit from mx-search')
        if regulatory_inquiry:
            notes.append('regulatory summary from mx-search')
        if risk_flags:
            notes.append('risk flags from mx-search')
        return RiskEnrichmentResult(
            audit_opinion=audit_opinion,
            regulatory_inquiry=regulatory_inquiry,
            risk_flags=risk_flags,
            source_notes=notes,
            query=query,
        )

    @staticmethod
    def _build_search_query(name: str, symbol: str) -> str:
        label = f'{name} {symbol}'.strip() or symbol or name or '该股票'
        return f'{label} 审计意见 问询函 立案 调查 处罚 监管措施 风险提示'

    @staticmethod
    def _extract_search_text(result: MXServiceResult) -> str:
        raw = result.raw or {}
        stdout = str(raw.get('stdout') or '')
        preview = '\n'.join(result.parsed.get('preview') or []) if isinstance(result.parsed, dict) else ''
        return '\n'.join([part for part in [stdout, preview] if part]).strip()

    @staticmethod
    def _extract_audit_from_search_text(text: str) -> str:
        clean = str(text or '')
        if '标准无保留意见' in clean or '无保留意见审计报告' in clean:
            return '标准无保留意见'
        if '无法表示意见' in clean:
            return '无法表示意见'
        if '否定意见' in clean:
            return '否定意见'
        if '保留意见' in clean:
            return '保留意见'
        return ''

    @staticmethod
    def _extract_regulatory_from_search_text(text: str) -> str:
        clean = str(text or '')
        hits = []
        for token in ['问询函', '问询', '立案', '处罚', '监管措施', '监管警示', '信披异常', '未及时披露']:
            if token in clean:
                hits.append(token)
        return '；'.join(dict.fromkeys(hits))

    def _extract_audit_opinion(self, tables: list[dict[str, Any]]) -> str:
        for table in tables:
            title = str(table.get('title') or table.get('frontendTitle') or '')
            field = table.get('field') or {}
            return_name = str(field.get('returnName') or '')
            if '审计意见' not in title and '审计意见' not in return_name:
                continue
            raw_table = table.get('table') or table.get('rawTable') or {}
            opinion_key = next((k for k in raw_table.keys() if k != 'headName'), '')
            values = raw_table.get(opinion_key) or []
            if values:
                return self._clean_text(values[0])
        return ''

    def _extract_regulatory_inquiry(self, tables: list[dict[str, Any]]) -> str:
        snippets: list[str] = []
        for table in tables:
            if not self._is_regulatory_table(table):
                continue
            raw_table = table.get('table') or table.get('rawTable') or {}
            head_names = raw_table.get('headName') or []
            for key, values in raw_table.items():
                if key == 'headName' or not isinstance(values, list):
                    continue
                row = {str(head_names[i]): self._clean_text(values[i]) for i in range(min(len(head_names), len(values)))}
                parts = [row.get('处分措施', ''), row.get('违规类型', ''), row.get('违规行为', '')]
                summary = '；'.join([p for p in parts if p])
                if summary:
                    snippets.append(summary)
        return '；'.join(dict.fromkeys(snippets))

    def _extract_risk_flags(self, tables: list[dict[str, Any]], audit_opinion: str, regulatory_inquiry: str) -> list[str]:
        flags: list[str] = []
        if self._is_bad_audit_opinion(audit_opinion):
            flags.append('审计意见异常')
        for table in tables:
            if not self._is_regulatory_table(table):
                continue
            raw_table = table.get('table') or table.get('rawTable') or {}
            text_chunks: list[str] = []
            for key, values in raw_table.items():
                if key == 'headName' or not isinstance(values, list):
                    continue
                text_chunks.extend([self._clean_text(v) for v in values])
            flags.extend(self._flags_from_text('；'.join(text_chunks)))
        flags.extend(self._flags_from_text(regulatory_inquiry))
        return list(dict.fromkeys([flag for flag in flags if flag]))

    @staticmethod
    def _is_bad_audit_opinion(audit: str) -> bool:
        text = str(audit or '').strip()
        if not text:
            return False
        if '标准无保留' in text or text == '无保留意见':
            return False
        return any(token in text for token in AUDIT_BAD_TOKENS)

    @staticmethod
    def _is_regulatory_table(table: dict[str, Any]) -> bool:
        title = str(table.get('title') or table.get('frontendTitle') or '')
        field = table.get('field') or {}
        return_name = str(field.get('returnName') or '')
        return_code = str(field.get('returnCode') or '')
        return any(token in (title + return_name + return_code) for token in ['违规', '处罚', '监管', '问询', '立案'])

    @staticmethod
    def _flags_from_text(text: str) -> list[str]:
        clean = str(text or '')
        flags = [flag for keyword, flag in RISK_KEYWORD_TO_FLAG.items() if keyword in clean]
        return list(dict.fromkeys(flags))

    @staticmethod
    def _clean_text(value: Any) -> str:
        if value is None:
            return ''
        text = str(value).strip()
        return '' if text.lower() == 'nan' else text
