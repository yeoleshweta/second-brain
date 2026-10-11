"""Anthropic Claude via HTTP — chat + wiki proposals. Never logs the key."""
from __future__ import annotations

import json
from typing import Any

import httpx
from loguru import logger

from src.config import get_settings

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

INVALID_KEY_HINT = (
    "Anthropic rejected ANTHROPIC_API_KEY. Create a key at "
    "https://console.anthropic.com/settings/keys, paste it into backend/.env "
    "as ANTHROPIC_API_KEY, and restart the backend."
)


def _httpx_error_message(exc: BaseException) -> str:
    resp = getattr(exc, "response", None)
    if resp is None:
        return ""
    try:
        data = resp.json()
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            return str(err.get("message") or "")
    except Exception:
        return ""
    return ""


def public_claude_error(exc: BaseException) -> str:
    status = getattr(exc, "response", None)
    code = getattr(status, "status_code", None) if status is not None else None
    msg = _httpx_error_message(exc).lower()
    if code == 401:
        return INVALID_KEY_HINT
    if code == 429 or "credit balance" in msg or "too low" in msg:
        return (
            "Claude has no API credits. Add billing at "
            "https://console.anthropic.com/settings/billing then retry Review."
        )
    if code:
        return f"Claude request failed (HTTP {code})."
    return "Claude request failed."


def key_health() -> dict[str, bool]:
    settings = get_settings()
    key = (settings.anthropic_api_key or "").strip()
    return {
        "anthropic_key_present": bool(key),
        "anthropic_key_format_ok": key.startswith("sk-ant-") and len(key) >= 20,
    }


async def probe_claude() -> dict[str, str | bool]:
    settings = get_settings()
    key = (settings.anthropic_api_key or "").strip()
    if not key:
        return {"ok": False, "code": "missing"}
    if not key_health()["anthropic_key_format_ok"]:
        return {"ok": False, "code": "malformed"}
    try:
        text = await complete(
            system="Reply with the single word ok.",
            user="ping",
            max_tokens=8,
        )
        return {"ok": True, "code": "ok" if text.strip() else "empty"}
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code == 401:
            return {"ok": False, "code": "invalid_api_key"}
        if code == 429:
            return {"ok": False, "code": "rate_limit_or_quota"}
        msg = _httpx_error_message(exc).lower()
        if "credit" in msg or "too low" in msg:
            return {"ok": False, "code": "billing"}
        return {"ok": False, "code": f"http_{code}"}
    except Exception:
        return {"ok": False, "code": "unreachable"}


async def complete(
    *,
    system: str,
    user: str,
    max_tokens: int = 1024,
    messages: list[dict[str, str]] | None = None,
) -> str:
    settings = get_settings()
    key = (settings.anthropic_api_key or "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    turns: list[dict[str, str]] = []
    for turn in messages or []:
        role = turn.get("role")
        content = turn.get("content")
        if role in {"user", "assistant"} and content:
            turns.append({"role": role, "content": str(content)})
    turns.append({"role": "user", "content": user})

    payload: dict[str, Any] = {
        "model": settings.anthropic_model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": turns,
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            ANTHROPIC_MESSAGES_URL,
            headers={
                "x-api-key": key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json=payload,
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            logger.warning("Claude HTTP {}", resp.status_code)
            raise
        data = resp.json()
    parts = data.get("content") or []
    texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "text"]
    return "".join(texts).strip()


def parse_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)
