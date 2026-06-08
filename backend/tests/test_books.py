"""Tests for free book integrations and Ross book handlers."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.agents.knowledge import (
    classify_sub_intent,
    handle_download_book,
    handle_find_book,
    handle_log_vocab,
    is_download_book_command,
    is_find_book_command,
)
from src.integrations.gutenberg import BookResult, pick_best_match, pick_read_format


def test_pick_read_format_prefers_plain_text() -> None:
    formats = {
        "application/epub+zip": "https://example.com/book.epub",
        "text/plain; charset=utf-8": "https://example.com/book.txt",
        "application/pdf": "https://example.com/book.pdf",
    }
    key, url = pick_read_format(formats)
    assert "text/plain" in key
    assert url.endswith(".txt")


def test_pick_best_match_by_title() -> None:
    books = [
        BookResult(id=1, title="Pride and Prejudice", authors=["Jane Austen"]),
        BookResult(id=2, title="Walden", authors=["Henry David Thoreau"]),
    ]
    match = pick_best_match(books, "Walden")
    assert match is not None
    assert match.id == 2


def test_find_book_intent() -> None:
    assert is_find_book_command("find free books on stoicism")
    assert classify_sub_intent("free books about philosophy") == "find_book"


def test_download_book_intent() -> None:
    assert is_download_book_command("download Meditations by Marcus Aurelius")
    assert is_download_book_command("download atomic habits")
    assert is_download_book_command("get dune")
    assert not is_download_book_command("download this article")
    assert classify_sub_intent("get free copy of Walden") == "download_book"
    assert classify_sub_intent("download atomic habits") == "download_book"


def test_extract_book_query_bible() -> None:
    from src.agents.knowledge import _extract_book_query

    assert _extract_book_query("download bible can you search for me") == "bible"
    assert _extract_book_query("download the holy bible") == "holy bible"
    assert "Meditations" in _extract_book_query('download "Meditations"')


def test_append_oceanofpdf_item_when_match() -> None:
    from src.agents.knowledge import _append_oceanofpdf_item
    from src.integrations.oceanofpdf import oceanofpdf_search_match

    items = [{"id": "openlibrary-OL1W", "downloadable": False, "source": "openlibrary"}]
    match = oceanofpdf_search_match("atomic habits")
    out = _append_oceanofpdf_item(items, "atomic habits", match)
    assert any(i.get("source") == "oceanofpdf" for i in out)
    oopdf = next(i for i in out if i.get("source") == "oceanofpdf")
    assert oopdf["url"] == "https://oceanofpdf.com/?s=atomic+habits"


def test_append_oceanofpdf_skipped_without_match() -> None:
    from src.agents.knowledge import _append_oceanofpdf_item

    items = [{"id": "openlibrary-OL1W", "downloadable": False}]
    out = _append_oceanofpdf_item(items, "Atomic Habits", None)
    assert not any(i.get("source") == "oceanofpdf" for i in out)


def test_is_strong_gutenberg_match() -> None:
    from src.agents.knowledge import _is_strong_gutenberg_match

    book = BookResult(id=1, title="Meditations", authors=["Marcus Aurelius"])
    assert _is_strong_gutenberg_match(book, "Meditations")
    assert not _is_strong_gutenberg_match(book, "Atomic Habits")


@pytest.fixture()
def session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Session:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from src.config.settings import get_settings

    get_settings.cache_clear()
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.mark.asyncio
async def test_handle_find_book_mocked(session: Session) -> None:
    gutenberg = [
        BookResult(
            id=2680,
            title="Meditations",
            authors=["Marcus Aurelius"],
            subjects=["Ethics", "Stoics"],
            formats={"text/plain; charset=utf-8": "https://example.com/med.txt"},
        )
    ]
    with (
        patch("src.agents.knowledge.search_gutenberg_broad", AsyncMock(return_value=gutenberg)),
        patch("src.agents.knowledge.search_open_library", AsyncMock(return_value=[])),
        patch("src.agents.knowledge.search_librivox", AsyncMock(return_value=[])),
    ):
        result = await handle_find_book("find free books on stoicism", session)
    assert "Meditations" in result["reply"]
    assert "Gutenberg" in result["reply"]
    assert len(result.get("book_items", [])) >= 1


@pytest.mark.asyncio
async def test_handle_download_book_mocked(session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from src.config.settings import get_settings

    get_settings.cache_clear()

    book = BookResult(
        id=2680,
        title="Meditations",
        authors=["Marcus Aurelius"],
        subjects=["Ethics", "Stoics"],
        formats={"text/plain; charset=utf-8": "https://example.com/med.txt"},
    )

    async def fake_save(item_id, **kwargs):
        from src.services.reading_content import write_markdown

        path = write_markdown(item_id, "# Meditations\n\nSample text")
        return path, "text"

    with (
        patch("src.agents.knowledge.search_gutenberg_broad", AsyncMock(return_value=[book])),
        patch("src.agents.knowledge.rc.save_gutenberg_book", side_effect=fake_save),
        patch("src.agents.knowledge.ObsidianClient") as mock_obs,
    ):
        mock_obs.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(create_note=AsyncMock()))
        mock_obs.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await handle_download_book("download Meditations", session)

    assert "Meditations" in result["reply"]
    assert (tmp_path / "reading").exists()


@pytest.mark.asyncio
async def test_handle_log_vocab(session: Session) -> None:
    with patch("src.agents.knowledge.ObsidianClient") as mock_obs:
        mock_obs.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(create_note=AsyncMock()))
        mock_obs.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await handle_log_vocab("log vocab: ephemeral — lasting a short time", session)
    assert "ephemeral" in result["reply"].lower()
