from __future__ import annotations

import pandas as pd


def is_star_st(name: str) -> bool:
    name = str(name or "")
    return name.startswith("*") or name.upper().startswith("*ST")


def is_st(name: str) -> bool:
    name = str(name or "").upper()
    return name.startswith("ST") or is_star_st(name)


def board_limit_ratio(
    symbol: str,
    name: str = "",
    list_date: str = "",
    delist_date: str = "",
    trade_date: str = "",
) -> float:
    code = str(symbol or "")
    name = str(name or "")
    list_date = str(list_date or "")
    delist_date = str(delist_date or "")
    trade_date = str(trade_date or "")

    if list_date and trade_date:
        try:
            if pd.to_datetime(trade_date) <= pd.to_datetime(list_date) + pd.Timedelta(days=4):
                return 1.0
        except Exception:
            pass

    if delist_date and trade_date:
        try:
            if pd.to_datetime(trade_date) >= pd.to_datetime(delist_date) - pd.Timedelta(days=30):
                return 0.10
        except Exception:
            pass

    if code.startswith(("sz300", "sh688")):
        return 0.20
    if code.startswith("bj"):
        return 0.30
    if is_st(name):
        return 0.05
    return 0.10
