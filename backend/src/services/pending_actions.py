"""In-memory pending-confirmation store.

Single-user app: one global pending action at a time is enough.
Actions expire after TTL to prevent stale confirmations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class PendingAction:
    kind: str               # "create_event" | "create_person" | "update_person"
    payload: dict[str, Any]
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(minutes=5))


_pending: PendingAction | None = None


def set_pending(kind: str, payload: dict[str, Any], ttl_minutes: int = 5) -> None:
    global _pending
    _pending = PendingAction(
        kind=kind,
        payload=payload,
        expires_at=datetime.now() + timedelta(minutes=ttl_minutes),
    )


def consume_pending() -> PendingAction | None:
    """Return and clear the pending action if it hasn't expired."""
    global _pending
    if not _pending or _pending.expires_at < datetime.now():
        _pending = None
        return None
    p, _pending = _pending, None
    return p


def peek_pending() -> PendingAction | None:
    """Return the pending action without consuming it, or None if expired."""
    global _pending
    if _pending and _pending.expires_at < datetime.now():
        _pending = None
    return _pending


def clear_pending() -> None:
    global _pending
    _pending = None
