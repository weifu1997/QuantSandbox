from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MXServiceResult:
    ok: bool
    tool: str
    query: str
    raw: dict[str, Any] = field(default_factory=dict)
    parsed: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error_message: str | None = None
