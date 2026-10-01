"""Rachel — Career agent.

Read-and-converse against Career/Profile and Context/career.md.
Does not write Profile/ or Context/. Does not file notes yet.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from openai import AsyncOpenAI

from src.config import get_settings
from src.services.career_profile import load_career_context

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState

SYSTEM_PROMPT = """You are Rachel, the career agent in Central Perk.

Voice: ambitious, practical, warm. Short replies (2–5 sentences) unless they
ask for a plan. Light "Oh my God" is fine; not a sitcom bit every message.

You CAN:
- Answer from the career profile and context files provided below.
- Help think through skills, goals, target paths, interviews, and next steps.
- Propose edits to Career/Profile/*.md as markdown the user can paste.

You CANNOT:
- Write to Career/Profile/ or Context/. The user owns those folders.
- Claim you saved, filed, or scored an article. Capture/filing are not wired.
- Invent work history or skills that are not in the profile. If a file is
  still a template, say so and ask them to fill Career/Profile/.

If the profile is empty, the next step is writing those four files by hand.
Do not pretend you already know their background."""

RACHEL_CHAT_SYSTEM = SYSTEM_PROMPT


async def handle_chat(msg: str, history: list[dict] | None = None) -> dict:
    settings = get_settings()
    try:
        profile_block, usable = await load_career_context()
    except Exception as exc:
        logger.warning("Rachel profile load failed: {}", exc)
        profile_block = "(Could not reach the Obsidian vault.)"
        usable = False

    system = RACHEL_CHAT_SYSTEM + "\n\n---\nCareer profile (read-only):\n" + profile_block
    if not usable:
        system += (
            "\n\nThe profile is still a template or missing. Be honest about that. "
            "Ask them to fill Career/Profile/{background,skills,goals,paths}.md."
        )

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for turn in (history or [])[-8:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": msg})

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model_cheap,
            messages=messages,
            max_tokens=700,
        )
        reply = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("Rachel LLM error: {}", exc)
        reply = (
            "I'm Rachel — career side of Central Perk. I couldn't reach the model just now. "
            "Your profile lives in `Career/Profile/`. Try me again in a second."
        )

    return {"reply": reply, "obsidian_path": None, "intent": "career"}


async def run(state: AgentState) -> dict:
    msg = state.get("user_message", "")
    history = state.get("chat_history") or []
    return await handle_chat(msg, history)
