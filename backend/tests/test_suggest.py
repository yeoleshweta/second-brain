"""Tests for interactive reading suggestions."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.agents.knowledge import classify_sub_intent, handle_suggest, is_suggest_command
from src.integrations.knowledge_sources import KnowledgeItem
from src.services import reading_list as rl
from src.storage.models import ItemKind, ItemStatus


def test_suggest_today_intent() -> None:
    assert is_suggest_command("suggest me a few things to read today")[0]
    assert classify_sub_intent("suggest me a few things to read today") == "suggest"


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.mark.asyncio
async def test_handle_suggest_returns_selectable_items(session: Session) -> None:
    rl.add(
        session,
        url="https://example.com/saved",
        title="Saved Article",
        summary="A deep dive into stoic philosophy and daily practice.",
        source="example.com",
        kind=ItemKind.URL,
        tags="philosophy",
    )

    feed_item = KnowledgeItem(
        title="Fresh AI Paper",
        url="https://arxiv.org/abs/9999.00001",
        summary="New benchmark results for reasoning models in 2026.",
        source="arXiv",
        published=datetime.now(),
        genre="ai",
    )

    with patch(
        "src.agents.knowledge._fetch_digest_candidates",
        AsyncMock(return_value=[feed_item]),
    ):
        result = await handle_suggest("suggest me a few things to read today", session)

    assert "suggest_items" in result
    items = result["suggest_items"]
    assert len(items) <= 3
    assert any(i["title"] == "Saved Article" for i in items)
    assert any(i["title"] == "Fresh AI Paper" for i in items)
    saved = next(i for i in items if i["title"] == "Saved Article")
    fresh = next(i for i in items if i["title"] == "Fresh AI Paper")
    assert saved["in_list"] is True
    assert fresh["in_list"] is False
    assert saved["summary"]
    assert fresh["summary"]
    assert fresh["est_minutes"] >= 3
    assert items[0]["title"] == "Fresh AI Paper"
