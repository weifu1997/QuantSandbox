from __future__ import annotations

from enum import Enum


class WorkflowType(str, Enum):
    LOW_VALUE = "low_value_discovery"
    BOTTOM_CONFIRM = "bottom_confirm"
    POSITION_MANAGE = "position_manage"
    CATALYST_AMBUSH = "catalyst_ambush"
