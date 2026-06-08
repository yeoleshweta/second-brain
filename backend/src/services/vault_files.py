"""Copy chat uploads into the Obsidian vault and create capture notes."""
from __future__ import annotations

import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.config import get_settings
from src.integrations.obsidian import ObsidianClient

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"}


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w.\-()+ ]", "_", name).strip(" .")
    return cleaned[:120] or "upload"


def vault_root() -> Path:
    settings = get_settings()
    if not settings.obsidian_vault_path:
        raise RuntimeError("OBSIDIAN_VAULT_PATH not set — required to store files in Obsidian")
    return Path(settings.obsidian_vault_path)


def is_image_path(path: Path) -> bool:
    return path.suffix.lower() in _IMAGE_EXTS


async def store_file_in_vault(
    src: Path,
    *,
    title: str,
    summary: str | None = None,
    user_note: str = "",
    tags: str = "",
) -> tuple[str, str]:
    """Copy file into vault Attachments/ and create a capture note.

    Returns (attachment_relative_path, capture_note_relative_path).
    """
    if not src.exists():
        raise FileNotFoundError(f"Upload not found: {src}")

    now = datetime.now()
    day = now.strftime("%Y-%m-%d")
    root = vault_root()
    dest_dir = root / "Attachments" / day
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_name = f"{uuid.uuid4().hex[:8]}-{_safe_filename(src.name)}"
    dest = dest_dir / dest_name
    shutil.copy2(src, dest)

    rel_attachment = f"Attachments/{day}/{dest_name}"
    note_slug = _safe_filename(src.stem)[:40] or "capture"
    note_rel = f"00-Inbox/Captured/{now.strftime('%Y-%m-%d-%H%M')}-{note_slug}.md"

    embed = (
        f"![[{rel_attachment}]]"
        if is_image_path(src)
        else f"[[{rel_attachment}|{src.name}]]"
    )

    tag_line = tags.strip()
    if tag_line and not tag_line.startswith("["):
        tag_line = f"[{tag_line}]"

    body_parts = [
        "---",
        f"captured: {now.isoformat()}",
        "source: chat-upload",
        f"file: {rel_attachment}",
    ]
    if tag_line:
        body_parts.append(f"tags: {tag_line}")
    body_parts.extend(["---", "", f"# {title}", ""])
    if summary:
        body_parts.extend([summary, ""])
    if user_note.strip():
        body_parts.extend([user_note.strip(), ""])
    body_parts.append(embed)
    body_parts.append("")
    content = "\n".join(body_parts)

    async with ObsidianClient() as obsidian:
        await obsidian.create_note(note_rel, content)

    logger.info("Vault capture {} -> {}", rel_attachment, note_rel)
    return rel_attachment, note_rel
