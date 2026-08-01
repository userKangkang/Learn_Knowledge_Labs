"""In-memory cancel flags for in-flight LLM streams (single-process MVP)."""

from __future__ import annotations

import threading

_lock = threading.Lock()
_cancelled: set[str] = set()


def request_cancel(request_id: str) -> None:
    with _lock:
        _cancelled.add(request_id)


def is_cancelled(request_id: str) -> bool:
    with _lock:
        return request_id in _cancelled


def clear_cancel(request_id: str) -> None:
    with _lock:
        _cancelled.discard(request_id)
