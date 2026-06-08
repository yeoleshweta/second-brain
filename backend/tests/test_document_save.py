"""Tests for uploaded document detection and save routing."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.agents.knowledge import (
    _infer_attachment_type,
    _is_reading_attachment,
    classify_sub_intent,
    handle_save,
    is_save_command,
)


@pytest.mark.parametrize(
    ("attachment", "expected"),
    [
        ({"media_type": "application/pdf", "filename": "paper.pdf"}, "pdf"),
        ({"media_type": "application/octet-stream", "filename": "paper.pdf"}, "pdf"),
        ({"media_type": "text/plain", "filename": "notes.txt"}, "text"),
        ({"media_type": "application/octet-stream", "filename": "readme.md"}, "text"),
        (
            {
                "media_type": "application/octet-stream",
                "filename": "report.docx",
            },
            "docx",
        ),
        ({"media_type": "image/jpeg", "filename": "receipt.jpg"}, "image"),
    ],
)
def test_infer_attachment_type(attachment: dict, expected: str) -> None:
    assert _infer_attachment_type(attachment) == expected


def test_is_reading_attachment() -> None:
    assert _is_reading_attachment({"filename": "a.pdf", "media_type": "application/pdf"})
    assert _is_reading_attachment({"filename": "b.txt", "media_type": "text/plain"})
    assert not _is_reading_attachment({"filename": "photo.jpg", "media_type": "image/jpeg"})


def test_save_document_phrases() -> None:
    assert is_save_command("save this document")
    assert is_save_command("save this pdf")


def test_classify_attachment_only_as_save() -> None:
    assert classify_sub_intent("", attachments=[{"file_id": "x", "filename": "a.pdf"}]) == "save"


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
async def test_handle_save_uploaded_pdf(
    session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path
    upload_dir = data_dir / "uploads"
    upload_dir.mkdir(parents=True)
    pdf_path = upload_dir / "abc123.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")

    monkeypatch.setenv("DATA_DIR", str(data_dir))
    from src.config.settings import get_settings

    get_settings.cache_clear()

    result = await handle_save(
        "save in notes",
        session,
        attachments=[{"file_id": "abc123", "filename": "paper.pdf", "media_type": "application/pdf"}],
    )
    assert "Saved" in result["reply"]
    assert (data_dir / "reading").exists()
