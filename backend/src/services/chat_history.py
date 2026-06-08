"""Persist chat sessions and messages in SQLite."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from src.storage.models import ChatMessage, ChatSession

MAX_TITLE_LEN = 56


def _now() -> datetime:
    return datetime.now()


def title_from_message(message: str) -> str:
    compact = " ".join(message.split())
    if not compact:
        return "New chat"
    if len(compact) <= MAX_TITLE_LEN:
        return compact
    return compact[: MAX_TITLE_LEN - 1].rstrip() + "…"


def create_session(db: Session, *, title: str = "New chat") -> ChatSession:
    now = _now()
    row = ChatSession(id=str(uuid.uuid4()), title=title, created_at=now, updated_at=now)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_session(db: Session, session_id: str) -> ChatSession | None:
    return db.get(ChatSession, session_id)


def list_sessions(db: Session, *, limit: int = 30) -> list[ChatSession]:
    stmt = select(ChatSession).order_by(ChatSession.updated_at.desc()).limit(limit)
    return list(db.exec(stmt).all())


def touch_session(db: Session, session: ChatSession, *, title: str | None = None) -> ChatSession:
    session.updated_at = _now()
    if title and (session.title == "New chat" or not session.title.strip()):
        session.title = title
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def maybe_set_title_from_first_message(db: Session, session: ChatSession, message: str) -> None:
    if session.title != "New chat":
        return
    touch_session(db, session, title=title_from_message(message))


def list_messages(db: Session, session_id: str) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return list(db.exec(stmt).all())


def append_message(
    db: Session,
    session_id: str,
    *,
    role: str,
    content: str,
    intent: str | None = None,
    extra: dict[str, Any] | None = None,
) -> ChatMessage:
    row = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role=role,
        content=content,
        intent=intent,
        extra_json=json.dumps(extra) if extra else None,
        created_at=_now(),
    )
    db.add(row)
    session = db.get(ChatSession, session_id)
    if session:
        session.updated_at = _now()
        db.add(session)
    db.commit()
    db.refresh(row)
    return row


def recent_history(db: Session, session_id: str, *, limit: int = 20) -> list[dict[str, str]]:
    rows = list_messages(db, session_id)
    complete = [r for r in rows if r.content.strip() and r.role in {"user", "assistant"}]
    out: list[dict[str, str]] = []
    for r in complete[-limit:]:
        row: dict[str, str] = {"role": r.role, "content": r.content}
        if r.intent:
            row["intent"] = r.intent
        out.append(row)
    return out


def last_assistant_intent(db: Session, session_id: str) -> str | None:
    rows = list_messages(db, session_id)
    for r in reversed(rows):
        if r.role == "assistant" and r.intent:
            return r.intent
    return None


def message_to_api(row: ChatMessage) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    if row.extra_json:
        try:
            extra = json.loads(row.extra_json)
        except json.JSONDecodeError:
            extra = {}
    return {
        "id": row.id,
        "role": row.role,
        "content": row.content,
        "intent": row.intent,
        "created_at": row.created_at.isoformat(),
        **extra,
    }


def session_to_api(row: ChatSession, *, message_count: int = 0) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "message_count": message_count,
    }
