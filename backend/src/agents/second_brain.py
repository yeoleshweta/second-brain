"""One Second Brain agent — capture-first, one vault, one daily note."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from src.config import get_settings
from src.integrations.obsidian import DAILY_NOTE_DIR

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState

SYSTEM_PROMPT = """You are the user's Second Brain — one assistant, one vault, one daily note.

You answer helpfully and concisely (1–3 short paragraphs unless they ask for more).
This is a personal capture-first system:

- Markdown in the Obsidian vault is the source of truth. SQLite is chat history only.
- Structured writes go only under ## Log in today's daily note: 00-Inbox/Daily/YYYY-MM-DD.md.
- Five log types only: food, finance, idea, task, exercise.
- Unparseable captures go to 00-Inbox/Unsorted/. Failures go to 99-System/Logs/.
- You never file into 01–05, Career/Profile, or Context. Structure emerges from human review later.
- If they ask to remember / capture / write this down, acknowledge the Inbox save briefly.
- Do not invent character names, specialist personas, or sitcom branding.
- Do not claim you created atomic notes in 01-Knowledge or any domain folder.

If today's daily note is provided below, use it so replies stay relevant.
Do not rewrite existing log lines."""

_DAILY_CONTEXT_CHARS = 4000


def _today_daily_path() -> str:
    return f"{DAILY_NOTE_DIR}/{datetime.now().strftime('%Y-%m-%d')}.md"


def _read_today_daily_note() -> str:
    """Read today's daily note from disk if it exists. Never create it."""
    settings = get_settings()
    if not settings.obsidian_vault_path:
        return ""
    path = Path(settings.obsidian_vault_path) / _today_daily_path()
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.debug("Could not read today's daily note: {}", type(exc).__name__)
        return ""


def _build_system_message(daily: str) -> str:
    if not daily.strip():
        return SYSTEM_PROMPT
    clipped = daily[:_DAILY_CONTEXT_CHARS]
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"Today's daily note (`{_today_daily_path()}`):\n"
        f"{clipped}"
    )


async def run(state: AgentState) -> dict:
    """Single chat node: answer helpfully; inbox capture happens after this in handle_message."""
    from openai import AsyncOpenAI

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    daily = _read_today_daily_note()
    messages: list[dict[str, str]] = [{"role": "system", "content": _build_system_message(daily)}]
    for turn in (state.get("chat_history") or [])[-8:]:
        role = turn.get("role")
        content = turn.get("content")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": str(content)})
    messages.append({"role": "user", "content": state["user_message"]})

    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model_cheap,
            messages=messages,
            max_tokens=512,
        )
        reply = resp.choices[0].message.content or "I'm here. What's on your mind?"
    except Exception as exc:
        logger.warning("Second Brain LLM error: {}", type(exc).__name__)
        reply = (
            "I couldn't reach the model just now. You can still capture with "
            "“remember this…” or “write this down…” — that goes to today's Inbox daily note."
        )

    return {"reply": reply, "obsidian_path": None, "intent": "general"}
