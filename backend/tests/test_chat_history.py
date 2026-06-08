"""Tests for chat session persistence."""
from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.services import chat_history as chat_store


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_create_session_and_messages(session: Session) -> None:
    row = chat_store.create_session(session, title="Test")
    chat_store.append_message(session, row.id, role="user", content="hi ross")
    chat_store.append_message(
        session,
        row.id,
        role="assistant",
        content="Hey!",
        intent="knowledge",
        extra={"bookItems": [{"id": "x"}]},
    )

    msgs = chat_store.list_messages(session, row.id)
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[1].intent == "knowledge"

    history = chat_store.recent_history(session, row.id)
    assert len(history) == 2
    assert history[0]["content"] == "hi ross"


def test_title_from_message() -> None:
    assert chat_store.title_from_message("download atomic habits") == "download atomic habits"
    long = "a" * 80
    assert len(chat_store.title_from_message(long)) <= 56
