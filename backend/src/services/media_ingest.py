"""Turn image/audio attachments into text the classifier and agents can read."""
from __future__ import annotations

from loguru import logger

from src.integrations.image_caption import describe_image
from src.integrations.speech import transcribe_audio
from src.services.uploads import infer_attachment_kind, resolve_uploaded_file


async def enrich_user_message(message: str, attachments: list[dict] | None) -> str:
    """Append transcripts and image descriptions. Never raises."""
    parts: list[str] = []
    for att in attachments or []:
        kind = infer_attachment_kind(att)
        file_id = str(att.get("file_id") or att.get("id") or "")
        path = resolve_uploaded_file(file_id)
        name = str(att.get("filename") or att.get("name") or kind)
        if path is None:
            continue
        try:
            if kind == "audio":
                text = await transcribe_audio(path)
                if text:
                    parts.append(f"[Voice message]: {text}")
                else:
                    parts.append("[Voice message]: (could not transcribe)")
            elif kind == "image":
                caption = await describe_image(path, user_hint=message)
                parts.append(f"[Image {name}]: {caption}")
        except Exception as exc:
            logger.warning("media enrich failed for {}: {}", name, exc)

    if not parts:
        return message
    base = message.strip()
    extra = "\n".join(parts)
    if not base:
        return extra
    return f"{base}\n\n{extra}"
