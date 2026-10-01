"""Speech: Whisper transcription and OpenAI TTS."""
from __future__ import annotations

import re
from pathlib import Path

from loguru import logger
from openai import AsyncOpenAI

from src.config import get_settings

INTENT_VOICE: dict[str, str] = {
    "knowledge": "onyx",
    "health": "nova",
    "calendar": "echo",
    "finance": "echo",
    "career": "shimmer",
    "general": "alloy",
}

_MD_FENCE = re.compile(r"```[\s\S]*?```")
_MD_MARK = re.compile(r"[*_`#>]+")
_URL = re.compile(r"https?://\S+")


def plain_for_speech(text: str, *, limit: int = 4000) -> str:
    cleaned = _MD_FENCE.sub(" ", text)
    cleaned = _URL.sub(" link ", cleaned)
    cleaned = _MD_MARK.sub(" ", cleaned)
    cleaned = " ".join(cleaned.split())
    return cleaned[:limit]


async def transcribe_audio(path: Path) -> str:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        with path.open("rb") as fh:
            resp = await client.audio.transcriptions.create(
                model=settings.openai_transcribe_model,
                file=fh,
            )
        return (getattr(resp, "text", None) or str(resp)).strip()
    except Exception as exc:
        from openai import AuthenticationError

        status = getattr(exc, "status_code", None)
        logger.warning(
            "Transcription failed for {} ({} {})",
            path,
            type(exc).__name__,
            status or "no-status",
        )
        if isinstance(exc, AuthenticationError):
            raise
        return ""


async def synthesize_speech(text: str, *, intent: str | None = None) -> bytes:
    settings = get_settings()
    voice = INTENT_VOICE.get(intent or "general", "alloy")
    spoken = plain_for_speech(text)
    if not spoken:
        spoken = "No reply to read."
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.audio.speech.create(
        model=settings.openai_tts_model,
        voice=voice,
        input=spoken,
        response_format="mp3",
    )
    return resp.content
