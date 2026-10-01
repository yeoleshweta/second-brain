"""OpenAI key health — never log or return the secret."""
from __future__ import annotations

from openai import APIStatusError, AsyncOpenAI, AuthenticationError, RateLimitError

from src.config import get_settings

INVALID_KEY_HINT = (
    "OpenAI rejected OPENAI_API_KEY (401 invalid_api_key). "
    "Create a new secret key at https://platform.openai.com/api-keys, "
    "paste it into backend/.env as OPENAI_API_KEY, and restart the backend."
)


def public_openai_error(exc: BaseException) -> str:
    """User-facing error without the key fingerprint OpenAI puts in 401 bodies."""
    if isinstance(exc, AuthenticationError):
        return INVALID_KEY_HINT
    if isinstance(exc, RateLimitError):
        return (
            "OpenAI rate limit or quota. Check billing at "
            "https://platform.openai.com/account/billing."
        )
    status = getattr(exc, "status_code", None)
    if status:
        return f"OpenAI request failed (HTTP {status})."
    return "OpenAI request failed."


def key_health() -> dict[str, bool]:
    settings = get_settings()
    return {
        "openai_key_present": settings.openai_key_present,
        "openai_key_format_ok": settings.openai_key_format_ok,
    }


async def probe_openai() -> dict[str, str | bool]:
    settings = get_settings()
    key = settings.openai_api_key
    if not key:
        return {"ok": False, "code": "missing"}
    if not settings.openai_key_format_ok:
        return {"ok": False, "code": "malformed"}
    client = AsyncOpenAI(api_key=key)
    try:
        await client.models.list()
        return {"ok": True, "code": "ok"}
    except AuthenticationError:
        return {"ok": False, "code": "invalid_api_key"}
    except RateLimitError:
        return {"ok": False, "code": "rate_limit_or_quota"}
    except APIStatusError as exc:
        return {"ok": False, "code": f"http_{exc.status_code}"}
    except Exception:
        return {"ok": False, "code": "unreachable"}
