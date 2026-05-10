from __future__ import annotations

from pydantic import BaseModel, Field


class BottomConfirmInput(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    left_side_preference: bool = True
    right_side_preference: bool = False
    user_id: str | None = None
