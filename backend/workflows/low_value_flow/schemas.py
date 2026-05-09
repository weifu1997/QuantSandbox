from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LowValueTemplate:
    market_scope: str = "全A"
    exclude_st: bool = True
    exclude_kechuang: bool = True
    exclude_chuangye: bool = True
    exclude_beijing: bool = True
    pe_lt: float = 20
    pb_lt: float = 2
    dividend_yield_gt: float = 2
    month_return_lt: float = -8


@dataclass
class LowValueRunInput:
    use_default_template: bool = True
    custom_query: str | None = None
    template: LowValueTemplate | None = None
    user_id: str | None = None


def build_default_query(template: LowValueTemplate | None = None) -> str:
    t = template or LowValueTemplate()
    excludes: list[str] = []
    if t.exclude_st:
        excludes.append("ST")
    if t.exclude_kechuang:
        excludes.append("科创板")
    if t.exclude_chuangye:
        excludes.append("创业板")
    if t.exclude_beijing:
        excludes.append("北交所")
    exclude_part = "、".join(excludes)
    return (
        f"{t.market_scope}中筛选 PE小于{t.pe_lt}、PB小于{t.pb_lt}、股息率大于{t.dividend_yield_gt}%"
        f"、近1月跌幅大于{abs(t.month_return_lt)}%的股票，排除{exclude_part}。"
    )
