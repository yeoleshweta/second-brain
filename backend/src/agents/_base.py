"""Shared helpers for agent implementations."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState

# Thought dumps only — five log types via append_to_inbox; never 01–05.
INBOX_CAPTURE_RE = re.compile(
    r"\b("
    r"remember this|capture this|note this|dump this|"
    r"write this down|put this in (?:my )?inbox|add to inbox|"
    r"inbox this"
    r")\b",
    re.IGNORECASE,
)


def is_inbox_capture(message: str) -> bool:
    """True when the user is dumping a thought to Inbox (not filing an article)."""
    return bool(INBOX_CAPTURE_RE.search(message or ""))


def is_inbox_thought_dump(message: str) -> bool:
    """Inbox dump, excluding article/file/URL saves."""
    if not is_inbox_capture(message):
        return False
    lowered = (message or "").lower()
    if "http://" in lowered or "https://" in lowered:
        return False
    return not bool(re.search(r"\b(article|blog|pdf|document|reading list)\b", lowered))


async def try_obsidian_capture(message: str, agent_name: str) -> str | None:
    """Best-effort Obsidian inbox capture — never raises, returns path or None."""
    try:
        from src.integrations import ObsidianClient

        async with ObsidianClient() as client:
            path = await client.append_to_inbox(message, source="user")
        return path
    except Exception as exc:
        logger.warning("Obsidian capture skipped ({}): {}", agent_name, exc)
        return None


async def stub_run(state: AgentState, agent_name: str) -> dict:
    """Legacy stub — captures to Obsidian but never crashes if Obsidian is down."""
    path = await try_obsidian_capture(state["user_message"], agent_name)
    if path:
        return {
            "reply": f"({agent_name} agent) Captured to `{path}`",
            "obsidian_path": path,
        }
    return {
        "reply": (
            f"({agent_name} agent) Got it — Obsidian isn't running so I couldn't "
            "save this, but I heard you."
        ),
        "obsidian_path": None,
    }
