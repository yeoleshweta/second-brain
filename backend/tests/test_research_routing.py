"""Research vs book download routing."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.agents.knowledge import (
    MAX_SUGGEST_ITEMS,
    _collect_suggest_items,
    _extract_book_query,
    _extract_research_topic,
    _feed_item_to_suggest,
    _is_likely_book_title,
    _pdf_preview_url,
    _topic_relevance_score,
    _topic_search_terms,
    classify_sub_intent,
    handle_research_search,
    is_download_book_command,
    is_research_command,
)
from src.integrations.knowledge_sources import KnowledgeItem


def test_research_not_download_book() -> None:
    assert is_research_command("find papers on transformers")
    assert not is_download_book_command("find papers on transformers")
    assert classify_sub_intent("find papers on transformers") == "research_search"


def test_download_book_still_works() -> None:
    assert classify_sub_intent("download atomic habits") == "download_book"
    assert classify_sub_intent("help me read verity") == "download_book"


def test_vague_add_this_not_book_title() -> None:
    assert not _is_likely_book_title("add this")
    assert _extract_book_query("add this to the list of things that you are") == ""


def test_research_topic_extraction() -> None:
    assert "transformers" in _extract_research_topic("find papers on transformers").lower()
    assert "climate" in _extract_research_topic("research articles about climate").lower()


def test_pdf_preview_for_arxiv() -> None:
    url = "https://arxiv.org/abs/2312.00752"
    preview = _pdf_preview_url(url)
    assert preview is not None
    assert "arxiv.org/pdf/" in preview


def test_feed_item_includes_pdf_preview() -> None:
    item = KnowledgeItem(
        title="Mamba",
        url="https://arxiv.org/abs/2312.00752",
        summary="State space model paper",
        source="arXiv",
    )
    row = _feed_item_to_suggest(item, existing_urls=set())
    assert row is not None
    assert row.get("pdf_preview_url")


def test_topic_relevance_prefers_matching_title() -> None:
    terms = _topic_search_terms("transformers")
    on_topic = KnowledgeItem(
        title="Attention Is All You Need for Transformers",
        url="https://example.com/a",
        summary="Neural architecture",
        source="web",
    )
    off_topic = KnowledgeItem(
        title="Climate modeling trends",
        url="https://example.com/b",
        summary="Weather patterns",
        source="web",
    )
    assert _topic_relevance_score(on_topic, terms) > _topic_relevance_score(off_topic, terms)


def test_collect_suggest_items_caps_at_three() -> None:
    items = [
        KnowledgeItem(
            title=f"Paper {i}",
            url=f"https://example.com/{i}",
            summary="transformers research",
            source="web",
        )
        for i in range(6)
    ]
    picked = _collect_suggest_items(items, existing_urls=set(), topic="transformers")
    assert len(picked) == MAX_SUGGEST_ITEMS


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.mark.asyncio
async def test_handle_research_search_returns_top_three(session: Session) -> None:
    feed = [
        KnowledgeItem(
            title=f"Transformers study {i}",
            url=f"https://arxiv.org/abs/2401.0000{i}",
            summary="Deep learning transformers",
            source="arXiv",
        )
        for i in range(5)
    ]
    with (
        patch("src.agents.knowledge.search_arxiv", AsyncMock(return_value=feed)),
        patch("src.agents.knowledge.search_tavily_with_options", AsyncMock(return_value=[])),
    ):
        result = await handle_research_search("find papers on transformers", session)

    assert len(result["suggest_items"]) == MAX_SUGGEST_ITEMS
