from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

from fastapi import HTTPException

logger = logging.getLogger(__name__)


@dataclass
class RateLimitRule:
    limit: int
    window_seconds: int
    concurrency_limit: int


_DEFAULT_RULES: dict[str, RateLimitRule] = {
    'data': RateLimitRule(limit=12, window_seconds=300, concurrency_limit=2),
    'search': RateLimitRule(limit=12, window_seconds=300, concurrency_limit=2),
    'xuangu': RateLimitRule(limit=6, window_seconds=300, concurrency_limit=1),
    'moni': RateLimitRule(limit=12, window_seconds=300, concurrency_limit=2),
}

_REQUEST_HISTORY: dict[tuple[str, str], deque[float]] = {}
_ACTIVE_COUNTS: dict[str, int] = {tool: 0 for tool in _DEFAULT_RULES}
_LOCK = threading.Lock()


def _client_key(explicit_user_id: str | None, client_host: str | None) -> str:
    value = (explicit_user_id or '').strip() or (client_host or '').strip() or 'anonymous'
    return value[:128]


def _configured_rule(tool: str) -> RateLimitRule:
    default = _DEFAULT_RULES[tool]
    prefix = f'QUANTSANDBOX_MX_{tool.upper()}_'
    try:
        limit = int(os.environ.get(prefix + 'RATE_LIMIT', default.limit))
        window = int(os.environ.get(prefix + 'RATE_WINDOW_SECONDS', default.window_seconds))
        concurrency = int(os.environ.get(prefix + 'CONCURRENCY_LIMIT', default.concurrency_limit))
    except ValueError:
        logger.warning('invalid MX limiter env for %s, using defaults', tool)
        return default
    return RateLimitRule(limit=max(limit, 1), window_seconds=max(window, 1), concurrency_limit=max(concurrency, 1))


def run_with_mx_limits(tool: str, explicit_user_id: str | None, client_host: str | None, func: Callable[[], object]) -> object:
    if tool not in _DEFAULT_RULES:
        return func()
    rule = _configured_rule(tool)
    client_key = _client_key(explicit_user_id, client_host)
    history_key = (tool, client_key)
    now = time.time()
    acquired_slot = False

    with _LOCK:
        history = _REQUEST_HISTORY.setdefault(history_key, deque())
        cutoff = now - rule.window_seconds
        while history and history[0] <= cutoff:
            history.popleft()
        if len(history) >= rule.limit:
            raise HTTPException(
                status_code=429,
                detail=f"MX {tool} 请求过于频繁，请在 {rule.window_seconds} 秒后重试",
            )
        active = _ACTIVE_COUNTS.get(tool, 0)
        if active >= rule.concurrency_limit:
            raise HTTPException(
                status_code=429,
                detail=f"MX {tool} 当前并发已满，请稍后再试",
            )
        history.append(now)
        _ACTIVE_COUNTS[tool] = active + 1
        acquired_slot = True

    try:
        return func()
    finally:
        if acquired_slot:
            with _LOCK:
                _ACTIVE_COUNTS[tool] = max(_ACTIVE_COUNTS.get(tool, 1) - 1, 0)
