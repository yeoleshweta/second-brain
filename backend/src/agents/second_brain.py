"""One Second Brain agent — Claude chat; wiki filing waits for human review."""
from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from src.config import get_settings

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState

SYSTEM_PROMPT = """You are the user's Second Brain — one assistant for an Obsidian LLM Wiki.

You answer helpfully and concisely (1–3 short paragraphs unless they ask for more).
Markdown in the vault is the source of truth.

Every user message is saved to Inbox/ as a raw note. Claude may draft a filing, but
nothing is written to Notes/, People/, Projects/, or Concepts/ until the user approves
it in Review. Do not claim you already filed a permanent note.

Use [[wiki-links]] in replies when you refer to people, projects, or concepts.
Do not invent specialist personas. Do not send email or create calendar events.

If a pending-review list is provided below, you may mention it briefly when relevant."""


def _build_system_message(pending_blurb: str) -> str:
    if not pending_blurb.strip():
        return SYSTEM_PROMPT
    return f"{SYSTEM_PROMPT}\n\nNotes waiting for your review:\n{pending_blurb[:2000]}"


async def _pending_blurb() -> str:
    try:
        from src.services.wiki import list_pending

        rows = await list_pending()
    except Exception as exc:
        logger.debug("pending review list skipped: {}", type(exc).__name__)
        return ""
    if not rows:
        return ""
    lines = [
        f"- `{r['path']}` ({r['status']}) → {r.get('destination') or 'no destination yet'}"
        for r in rows[:12]
    ]
    return "\n".join(lines)


async def run(state: AgentState) -> dict:
    from src.integrations.claude import complete, public_claude_error

    settings = get_settings()
    pending = await _pending_blurb()
    history = [
        {"role": str(t.get("role")), "content": str(t.get("content"))}
        for t in (state.get("chat_history") or [])[-8:]
        if t.get("role") in {"user", "assistant"} and t.get("content")
    ]
    try:
        if not settings.anthropic_key_present:
            reply = (
                "ANTHROPIC_API_KEY is not set. Add it to backend/.env and restart. "
                "Your message can still be saved to Inbox for review."
            )
        else:
            reply = await complete(
                system=_build_system_message(pending),
                user=state["user_message"],
                messages=history,
                max_tokens=1024,
            ) or "I'm here. What's on your mind?"
    except Exception as exc:
        logger.warning("Second Brain Claude error: {}", type(exc).__name__)
        reply = public_claude_error(exc)

    return {"reply": reply, "obsidian_path": None, "intent": "general"}
