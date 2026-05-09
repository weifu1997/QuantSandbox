from __future__ import annotations

CATALYST_KEYWORDS = {
    "分红": "高分红",
    "回购": "回购",
    "增持": "增持",
    "业绩": "业绩改善",
    "预增": "业绩改善",
    "扭亏": "业绩改善",
    "中标": "订单催化",
    "合同": "订单催化",
    "涨价": "价格催化",
    "景气": "行业景气",
    "扩产": "产能扩张",
    "新产能": "产能扩张",
    "新品": "新品催化",
    "创新药": "产品催化",
    "改革": "改革催化",
}


class CatalystExtractor:
    def derive_catalyst_factors(self, search_review_data: dict | list | str | None) -> list[str]:
        text_parts: list[str] = []
        if isinstance(search_review_data, dict):
            preview = search_review_data.get('preview')
            if isinstance(preview, list):
                text_parts.extend(str(x) for x in preview[:40])
            else:
                for v in search_review_data.values():
                    if isinstance(v, list):
                        text_parts.extend(str(x) for x in v[:20])
                    elif isinstance(v, str):
                        text_parts.append(v)
        elif isinstance(search_review_data, list):
            text_parts.extend(str(x) for x in search_review_data[:40])
        elif isinstance(search_review_data, str):
            text_parts.append(search_review_data)
        text = '\n'.join(text_parts)

        found: list[str] = []
        for kw, label in CATALYST_KEYWORDS.items():
            if kw in text and label not in found:
                found.append(label)
        return found[:4]
