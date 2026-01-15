"""Помощники ретраев для API вызовов."""

from __future__ import annotations

from typing import Iterator

from shared.constants import MAX_RETRY_DELAY, RETRY_BACKOFF_START


def backoff_delays() -> Iterator[int]:
    """Генерировать экспоненциальные задержки в секундах."""

    delay = RETRY_BACKOFF_START
    while True:
        yield delay
        delay = min(delay * 2, MAX_RETRY_DELAY)
