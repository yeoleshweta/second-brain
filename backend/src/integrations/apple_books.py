"""Apple Books via the apple-books-mcp server (read-only library + highlights)."""
from __future__ import annotations

import re

from loguru import logger

from src.config import get_settings
from src.integrations.mcp_stdio import call_mcp_tool

_SETUP_HINT = (
    "See `docs/mcp-apple-books.md` — allow macOS access when prompted, "
    "then restart the backend."
)


class AppleBooksError(RuntimeError):
    pass


def _mcp_args() -> tuple[str, list[str]]:
    settings = get_settings()
    args = [part.strip() for part in settings.apple_books_mcp_args.split(",") if part.strip()]
    return settings.apple_books_mcp_command, args


async def _call(tool: str, arguments: dict | None = None) -> str:
    command, args = _mcp_args()
    try:
        text = await call_mcp_tool(command, args, tool, arguments)
    except Exception as exc:
        logger.warning("Apple Books MCP {} failed: {}", tool, exc)
        raise AppleBooksError(f"Apple Books MCP error: {exc}") from exc
    if not text:
        raise AppleBooksError(
            f"Apple Books returned no data. {_SETUP_HINT}"
        )
    return text


async def books_in_progress(limit: int = 10) -> str:
    return await _call("get_books_in_progress", {"limit": limit})


async def recently_read(limit: int = 10) -> str:
    return await _call("get_recently_read_books", {"limit": limit})


async def library_stats() -> str:
    return await _call("get_library_stats")


async def list_books(limit: int = 25) -> str:
    return await _call("list_all_books", {"limit": limit})


async def recent_highlights(limit: int = 15) -> str:
    return await _call("recent_annotations", {"limit": limit})


async def search_highlights(text: str, limit: int = 15) -> str:
    return await _call("search_annotations", {"text": text, "limit": limit})


async def search_books(title: str, limit: int = 10) -> str:
    return await _call("search_books_by_title", {"title": title, "limit": limit})


def _extract_search_title(msg: str) -> str | None:
    for pat in (
        r"highlights?(?: from| in| on)?\s+(.{2,80}?)\s*[?.!]*$",
        r"annotations?(?: from| in| on)?\s+(.{2,80}?)\s*[?.!]*$",
        r"notes from\s+(.{2,80}?)\s*[?.!]*$",
        r"search (?:my )?books for\s+(.{2,80}?)\s*[?.!]*$",
        r"do i have\s+(.{2,80}?)\s+in (?:my )?books",
    ):
        m = re.search(pat, msg, re.IGNORECASE)
        if m:
            return m.group(1).strip(" '\"")
    return None


async def handle_apple_books_request(msg: str) -> dict:
    """Dispatch natural-language Apple Books queries for Ross."""
    lowered = msg.lower()

    try:
        if re.search(
            r"\b(library stats|reading stats|how many books|library summary)\b",
            lowered,
        ):
            body = await library_stats()
            return {"reply": f"📚 **Apple Books library**\n\n{body}"}

        if re.search(r"\b(list (?:all )?my books|my book library|all my books)\b", lowered):
            body = await list_books()
            return {"reply": f"📚 **Your Apple Books library**\n\n{body}"}

        title = _extract_search_title(msg)
        if title and re.search(r"\b(highlights?|annotations?|notes)\b", lowered):
            body = await search_highlights(title)
            return {"reply": f"📚 **Highlights — {title}**\n\n{body}"}

        if re.search(r"\b(highlights?|annotations?)\b", lowered):
            body = await recent_highlights()
            return {"reply": f"📚 **Recent Apple Books highlights**\n\n{body}"}

        if title or re.search(r"\bsearch (?:my )?books\b", lowered):
            query = title or _extract_search_title(msg) or msg
            body = await search_books(query)
            return {"reply": f"📚 **Apple Books search — {query}**\n\n{body}"}

        in_progress = await books_in_progress()
        recent = await recently_read(limit=5)
        return {
            "reply": (
                "📚 **Currently in Apple Books**\n\n"
                f"{in_progress}\n\n**Recently opened**\n\n{recent}"
            )
        }
    except AppleBooksError as exc:
        return {
            "reply": (
                f"📚 Ross: couldn't read Apple Books — {exc}\n\n{_SETUP_HINT}"
            )
        }
