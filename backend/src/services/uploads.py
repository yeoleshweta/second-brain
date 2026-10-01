"""Resolve chat uploads and classify attachment kind."""
from __future__ import annotations

from pathlib import Path

from src.config import get_settings

Kind = str  # audio | image | pdf | text | docx | document | unknown


def upload_dir() -> Path:
    path = Path(get_settings().data_dir) / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_uploaded_file(file_id: str) -> Path | None:
    if not file_id:
        return None
    matches = list(upload_dir().glob(f"{file_id}.*"))
    return matches[0] if matches else None


def attachment_filename(att: dict) -> str:
    return str(att.get("filename") or att.get("name") or "").strip()


def infer_attachment_kind(att: dict) -> Kind:
    media = (att.get("media_type") or "").lower().split(";")[0].strip()
    name = attachment_filename(att).lower()
    ext = Path(name).suffix if name else ""
    if (
        media.startswith("audio/")
        or media in {"video/mp4", "video/webm"}
        or ext in {".webm", ".m4a", ".mp3", ".wav", ".ogg", ".aac", ".mpga", ".mp4"}
    ):
        return "audio"
    if "pdf" in media or ext == ".pdf":
        return "pdf"
    if media.startswith("text/") or ext in {".txt", ".md", ".markdown"}:
        return "text"
    if ext in {".docx", ".doc"} or "wordprocessingml" in media:
        return "docx"
    if media.startswith("image/") or ext in {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".heic",
        ".heif",
    }:
        return "image"
    if ext in {".rtf", ".csv", ".json"}:
        return "document"
    return "unknown"


def is_document_attachment(att: dict) -> bool:
    return infer_attachment_kind(att) in {"pdf", "text", "docx", "document"}


def has_document_attachment(attachments: list[dict] | None) -> bool:
    return any(is_document_attachment(a) for a in (attachments or []))
