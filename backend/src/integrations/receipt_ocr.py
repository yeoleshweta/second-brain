"""Receipt OCR using Claude's vision capability.

Pass a receipt image (jpg/png/webp) and get structured items + total back.
This is dramatically simpler and more accurate than running Tesseract.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from anthropic import AsyncAnthropic
from loguru import logger
from pydantic import BaseModel

from src.config import get_settings


class ReceiptItem(BaseModel):
    name: str
    quantity: float | None = None
    unit_price: float | None = None
    total_price: float | None = None
    category: str | None = None


class ParsedReceipt(BaseModel):
    merchant: str | None = None
    date: str | None = None  # ISO date if detectable
    items: list[ReceiptItem]
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    raw_text: str = ""


_PROMPT = """Extract structured data from this receipt image.

Return ONLY valid JSON matching this schema:
{
  "merchant": "store name or null",
  "date": "YYYY-MM-DD or null",
  "items": [
    {
      "name": "item description",
      "quantity": number or null,
      "unit_price": number or null,
      "total_price": number or null,
      "category": "produce|dairy|meat|pantry|beverage|household|other"
    }
  ],
  "subtotal": number or null,
  "tax": number or null,
  "total": number or null
}

No markdown fences, no commentary, just the JSON object."""


async def parse_receipt(image_path: Path | bytes, media_type: str = "image/jpeg") -> ParsedReceipt:
    """Send a receipt image to Claude and parse the structured response."""
    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    if isinstance(image_path, Path):
        image_bytes = image_path.read_bytes()
        suffix = image_path.suffix.lower()
        media_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }.get(suffix, media_type)
    else:
        image_bytes = image_path

    image_b64 = base64.standard_b64encode(image_bytes).decode("ascii")

    logger.info("Parsing receipt ({} bytes, {})", len(image_bytes), media_type)
    resp = await client.messages.create(
        model=settings.anthropic_model_main,
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": _PROMPT},
                ],
            }
        ],
    )

    raw = resp.content[0].text.strip()  # type: ignore[union-attr]
    # Defensive: strip code fences if the model added them anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Receipt parsing returned invalid JSON: {}", raw[:200])
        raise ValueError(f"Could not parse receipt: {e}") from e

    return ParsedReceipt(**data, raw_text=raw)
