"""Tests for PDF download and save heuristics."""
from __future__ import annotations

from src.agents.knowledge import _should_save_as_pdf
from src.services.reading_content import _is_pdf_bytes, is_probable_pdf_url, resolve_pdf_url


def test_resolve_arxiv_pdf_url() -> None:
    url = "https://arxiv.org/abs/2312.00752"
    assert resolve_pdf_url(url) == "https://arxiv.org/pdf/2312.00752.pdf"


def test_is_jina_pdf_placeholder() -> None:
    from src.services.reading_content import is_jina_pdf_placeholder

    sample = (
        "Title:\n\nURL Source: https://spie.org/samples/paper.pdf\n\n"
        "Warning: This page contains iframe that are currently hidden, "
        "consider enabling iframe processing.\n\nMarkdown Content:\n"
    )
    assert is_jina_pdf_placeholder(sample)


def test_is_probable_pdf_url() -> None:
    assert is_probable_pdf_url("https://example.com/paper.pdf")
    assert is_probable_pdf_url("https://arxiv.org/abs/2312.00752")
    assert not is_probable_pdf_url("https://example.com/article")


def test_should_save_as_pdf_with_preview_url() -> None:
    assert _should_save_as_pdf(
        "https://example.com/article",
        kind="url",
        pdf_url="https://example.com/paper.pdf",
    )


def test_should_save_as_pdf_for_paper_kind_without_pdf_url() -> None:
    assert not _should_save_as_pdf("https://example.com/article", kind="paper")


def test_should_save_as_pdf_for_direct_pdf_url() -> None:
    assert _should_save_as_pdf("https://example.com/paper.pdf", kind="url")


def test_is_pdf_bytes_magic() -> None:
    assert _is_pdf_bytes(b"%PDF-1.4\n")
    assert not _is_pdf_bytes(b"<html>")
