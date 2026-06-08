"""Describe uploaded images for Obsidian capture notes."""
from __future__ import annotations

import base64
from pathlib import Path

from loguru import logger
from openai import AsyncOpenAI

from src.config import get_settings


async def describe_image(path: Path, *, user_hint: str = "") -> str:
    settings = get_settings()
    suffix = path.suffix.lower()
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".heic": "image/jpeg",
    }.get(suffix, "image/jpeg")

    image_b64 = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    prompt = (
        "Describe this image in 2-4 sentences for a personal knowledge base. "
        "Include any visible text, document type, or subject. Be factual."
    )
    if user_hint.strip():
        prompt += f" User context: {user_hint.strip()}"

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model_cheap,
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
                        },
                    ],
                }
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("Image caption failed: {}", exc)
        return "Image uploaded (auto-description unavailable)."
