"""Session intent stickiness and topic-aware search."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.agents.knowledge import (
    _extract_search_topic,
    classify_sub_intent,
    handle_topic_search,
    is_digest_command,
    is_topic_search_command,
)
from src.integrations.knowledge_sources import KnowledgeItem
from src.orchestrator.graph import _apply_session_intent_sticky


def test_stcw_question_not_generic_digest() -> None:
    msg = "What are the latest amendments to STCW code?"
    assert not is_digest_command(msg)
    assert classify_sub_intent(msg) == "topic_search"


def test_extract_stcw_topic() -> None:
    topic = _extract_search_topic("What are the latest amendments to STCW code?")
    assert topic is not None
    assert "stcw" in topic.lower()


def test_session_stickiness_keeps_ross() -> None:
    history = [
        {"role": "user", "content": "suggest me things to read"},
        {"role": "assistant", "content": "Here are picks", "intent": "knowledge"},
    ]
    intent = _apply_session_intent_sticky(
        "Show me what ThrustSSC looks like?",
        history,
        "general",
    )
    assert intent == "knowledge"


def test_session_stickiness_allows_explicit_monica() -> None:
    history = [
        {"role": "assistant", "content": "Saved.", "intent": "knowledge"},
    ]
    intent = _apply_session_intent_sticky(
        "Monica I had eggs for breakfast",
        history,
        "general",
    )
    assert intent == "health"


def test_topic_from_history_on_follow_up() -> None:
    history = [
        {"role": "user", "content": "What are the latest amendments to STCW code?"},
    ]
    assert is_topic_search_command("These are not related to what I asked", history)
    topic = _extract_search_topic("These are not related to what I asked", history)
    assert topic is not None
    assert "stcw" in topic.lower()


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.mark.asyncio
async def test_handle_topic_search_returns_fresh_topic_hits(session: Session) -> None:
    feed = [
        KnowledgeItem(
            title="STCW 2024 amendments overview",
            url="https://example.com/stcw-amendments",
            summary="Maritime training standards update for STCW code",
            source="IMO",
        ),
        KnowledgeItem(
            title="STCW refresher requirements",
            url="https://example.com/stcw-refresher",
            summary="Latest STCW certification guidance",
            source="maritime.gov",
        ),
        KnowledgeItem(
            title="OpenAI blog unrelated",
            url="https://openai.com/blog/unrelated",
            summary="AI tools",
            source="openai.com",
        ),
    ]
    with patch(
        "src.agents.knowledge._fetch_topic_sources",
        AsyncMock(return_value=feed),
    ):
        result = await handle_topic_search(
            "What are the latest amendments to STCW code?",
            session,
        )

    titles = [i["title"] for i in result["suggest_items"]]
    assert any("stcw" in t.lower() for t in titles)
    assert titles[0] == "STCW 2024 amendments overview"
