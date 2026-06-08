"""Tests for tagged feed configuration and topic filtering."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.integrations import knowledge_sources as ks
from src.integrations.knowledge_sources import (
    KnowledgeItem,
    balance_items_by_tag,
    extract_topic_tags_from_message,
    load_feed_sources,
    resolve_feed_sources,
)


@pytest.fixture(autouse=True)
def _clear_feed_cache() -> None:
    load_feed_sources.cache_clear()
    yield
    load_feed_sources.cache_clear()


def test_load_feed_sources_from_yaml() -> None:
    sources = load_feed_sources()
    assert len(sources) >= 20
    assert any("ai" in s.tags for s in sources)
    assert any("design" in s.tags for s in sources)


def test_extract_topic_tags_ai() -> None:
    tags = extract_topic_tags_from_message("what's new in AI today?")
    assert tags is not None
    assert "ai" in tags


def test_extract_topic_tags_business() -> None:
    tags = extract_topic_tags_from_message("any startup news?")
    assert tags is not None
    assert "business" in tags


def _mock_settings() -> object:
    backend_root = Path(__file__).resolve().parents[1]
    return type(
        "S",
        (),
        {
            "rss_feed_list": [],
            "knowledge_feeds_config": backend_root / "config" / "feeds.yaml",
        },
    )()


def test_resolve_feed_sources_filters_by_interest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.integrations.knowledge_sources.get_settings",
        _mock_settings,
    )
    sources = resolve_feed_sources(["ai", "engineering"])
    assert sources
    wanted = {"ai", "engineering"}
    assert all(wanted.intersection(set(s.tags)) for s in sources)


def test_resolve_feed_sources_topic_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.integrations.knowledge_sources.get_settings",
        _mock_settings,
    )
    all_sources = resolve_feed_sources(["ai", "business", "design"])
    design_only = resolve_feed_sources(["ai", "business", "design"], topic_tags=["design"])
    assert design_only
    assert all("design" in s.tags for s in design_only)
    assert len(design_only) <= len(all_sources)


def test_balance_items_by_tag() -> None:
    items = [
        KnowledgeItem(
            title=f"{tag}-{i}",
            url=f"https://example.com/{tag}/{i}",
            summary="",
            source="test",
            genre=tag,
        )
        for tag in ("ai", "business")
        for i in range(3)
    ]
    balanced = balance_items_by_tag(items, max_per_tag=2, max_total=4)
    assert len(balanced) == 4
    ai_count = sum(1 for i in balanced if i.genre == "ai")
    biz_count = sum(1 for i in balanced if i.genre == "business")
    assert ai_count == 2
    assert biz_count == 2
