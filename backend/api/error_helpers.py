from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def log_and_raise_http(status_code: int, user_message: str, *, exc: Exception, context: dict[str, Any] | None = None) -> None:
    logger.exception(user_message, extra={"context": context or {}, "status_code": status_code})
    raise HTTPException(status_code=status_code, detail=user_message) from exc
