from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.core.strategy import PositionTarget

logger = logging.getLogger(__name__)

LEGACY_SINGLE_TARGET_WARNING = (
    "LEGACY: strategy returned a single target; "
    "formal strategies MUST return per-bar targets (len(targets) == len(df)). "
    "Single-target fallback will be removed in v2.0."
)


def validate_per_bar_targets(
    targets: list["PositionTarget"],
    df_len: int,
    strategy_name: str,
    symbol: str,
) -> list["PositionTarget"]:
    """验证策略返回的 targets 是否符合逐 bar 契约。

    契约要求：
    - 正式策略必须返回 len(targets) == len(df)
    - 每个 target 的 metadata 必须包含 bar_date
    - 返回原始 targets（通过则不变，供链式调用）

    单 target 历史策略：len(targets)==1 且 df_len > 1 时打 warning，
    但允许通过（向后兼容期）。v2.0 会升格为错误。
    """
    if not targets:
        raise ValueError(
            f"{strategy_name} ({symbol}): generate_targets returned empty list. "
            f"Must return at least one PositionTarget."
        )

    if len(targets) == 1 and df_len > 1:
        logger.warning(
            f"{strategy_name} ({symbol}): {LEGACY_SINGLE_TARGET_WARNING}"
        )
        # Legacy/smoke: 单 target 允许缺少 bar_date（引擎会复制到所有 bar）
        return targets
    elif len(targets) != df_len:
        raise ValueError(
            f"{strategy_name} ({symbol}): target count {len(targets)} "
            f"does not match dataframe length {df_len}. "
            f"Formal strategies must return exactly one PositionTarget per bar."
        )

    # 正式策略：强制每个 target 带 bar_date
    for i, t in enumerate(targets):
        if not t.metadata.get("bar_date"):
            raise ValueError(
                f"{strategy_name} ({symbol}): target[{i}] missing "
                f"metadata.bar_date. All targets must carry bar_date."
            )

    return targets
