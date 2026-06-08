"""Tests for book discovery fallbacks."""
from __future__ import annotations

from src.integrations.book_discovery import (
    build_oceanofpdf_book_item,
    format_book_not_found_alternatives,
    legal_discovery_links,
)
from src.integrations.oceanofpdf import oceanofpdf_search_match


def test_legal_discovery_links() -> None:
    links = legal_discovery_links("Atomic Habits")
    labels = [label for label, _, _ in links]
    assert "Open Library" in labels
    assert "WorldCat" in labels


def test_not_found_includes_search_url() -> None:
    match = oceanofpdf_search_match("atomic habits")
    text = format_book_not_found_alternatives("atomic habits", oceanofpdf_match=match)
    assert "Ocean of PDF search" in text
    assert "oceanofpdf.com/?s=atomic+habits" in text


def test_oceanofpdf_book_item_uses_search_url() -> None:
    match = oceanofpdf_search_match("atomic habits")
    item = build_oceanofpdf_book_item("atomic habits", match)
    assert item["url"] == "https://oceanofpdf.com/?s=atomic+habits"
    assert item["source"] == "oceanofpdf"
