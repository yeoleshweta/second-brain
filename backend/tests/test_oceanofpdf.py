"""Tests for Ocean of PDF lookup."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.integrations.knowledge_sources import KnowledgeItem
from src.integrations.oceanofpdf import (
    OceanOfPdfMatch,
    _normalize_book_page_url,
    _score_candidate,
    _title_from_oceanofpdf_url,
    lookup_oceanofpdf_book_page,
    oceanofpdf_search_match,
    oceanofpdf_search_url,
    resolve_oceanofpdf,
)


def test_oceanofpdf_search_url() -> None:
    assert oceanofpdf_search_url("atomic habits") == "https://oceanofpdf.com/?s=atomic+habits"
    assert oceanofpdf_search_url("Atomic Habits") == "https://oceanofpdf.com/?s=Atomic+Habits"


def test_oceanofpdf_search_match() -> None:
    match = oceanofpdf_search_match("atomic habits")
    assert match.is_search is True
    assert match.url == "https://oceanofpdf.com/?s=atomic+habits"


def test_normalize_book_page_url() -> None:
    url = _normalize_book_page_url(
        "https://oceanofpdf.com/books/atomic-habits-pdf-james-clear/?ref=1"
    )
    assert url == "https://oceanofpdf.com/books/atomic-habits-pdf-james-clear/"


def test_title_from_url() -> None:
    assert _title_from_oceanofpdf_url(
        "https://oceanofpdf.com/books/atomic-habits-pdf-james-clear/"
    ) == "atomic habits"


def test_score_candidate_prefers_close_title() -> None:
    url = "https://oceanofpdf.com/books/atomic-habits-pdf-james-clear/"
    score = _score_candidate("Atomic Habits", url, "Atomic Habits PDF")
    assert score >= 0.45


@pytest.mark.asyncio
async def test_resolve_falls_back_to_search_url() -> None:
    with patch(
        "src.integrations.oceanofpdf.lookup_oceanofpdf_book_page",
        AsyncMock(return_value=None),
    ):
        match = await resolve_oceanofpdf("atomic habits")
    assert match.is_search is True
    assert match.url == "https://oceanofpdf.com/?s=atomic+habits"


@pytest.mark.asyncio
async def test_resolve_prefers_direct_book_page() -> None:
    direct = OceanOfPdfMatch(
        title="Atomic Habits",
        url="https://oceanofpdf.com/books/atomic-habits-pdf-james-clear/",
        score=0.9,
        is_search=False,
    )
    with patch(
        "src.integrations.oceanofpdf.lookup_oceanofpdf_book_page",
        AsyncMock(return_value=direct),
    ):
        match = await resolve_oceanofpdf("Atomic Habits")
    assert match.is_search is False
    assert "/books/" in match.url


@pytest.mark.asyncio
async def test_lookup_book_page_returns_match_when_search_finds_book() -> None:
    items = [
        KnowledgeItem(
            title="Atomic Habits by James Clear PDF",
            url="https://oceanofpdf.com/books/atomic-habits-pdf-james-clear/",
            summary="",
            source="Tavily",
        )
    ]
    with patch("src.integrations.oceanofpdf._search_web", AsyncMock(return_value=items)):
        match = await lookup_oceanofpdf_book_page("Atomic Habits")
    assert match is not None
    assert "atomic-habits" in match.url
    assert match.is_search is False


@pytest.mark.asyncio
async def test_lookup_book_page_returns_none_when_no_close_match() -> None:
    items = [
        KnowledgeItem(
            title="Unrelated Book",
            url="https://oceanofpdf.com/books/totally-different-pdf-author/",
            summary="",
            source="Tavily",
        )
    ]
    with patch("src.integrations.oceanofpdf._search_web", AsyncMock(return_value=items)):
        match = await lookup_oceanofpdf_book_page("Atomic Habits")
    assert match is None
