"""Tests for reading content storage."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.services import reading_content as rc


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from src.config.settings import get_settings

    get_settings.cache_clear()
    return tmp_path


def test_write_and_read_markdown(data_dir: Path) -> None:
    rel = rc.write_markdown(42, "# Hello\n\nWorld")
    assert rel.endswith("content.md")
    body = rc.read_markdown(rel)
    assert body is not None
    assert "Hello" in body
    assert (data_dir / "reading" / "42" / "content.md").exists()


def test_copy_pdf(data_dir: Path) -> None:
    src = data_dir / "upload.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    rel = rc.copy_pdf(7, src)
    assert rel.endswith("document.pdf")
    assert rc.read_pdf_bytes(rel) == b"%PDF-1.4 test"


def test_delete_item_content(data_dir: Path) -> None:
    rc.write_markdown(99, "note body")
    assert (data_dir / "reading" / "99").exists()
    rc.delete_item_content(99)
    assert not (data_dir / "reading" / "99").exists()
