"""Chandler — Finance Agent.

Phase 5 full implementation: Plaid sync, transaction analysis, weekly reviews.
For now: real conversational responses — can discuss money, budgets, and habits freely.

SECURITY: read-only. Never moves money. Never sends payments.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from openai import AsyncOpenAI

from src.agents._base import try_obsidian_capture
from src.config import get_settings

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState

SYSTEM_PROMPT = """You are Chandler, a sharp and slightly self-deprecating financial advisor \
in the user's personal AI second-brain app. You help with budgeting, spending awareness, \
savings strategies, and financial habits. You're knowledgeable but approachable — finance \
doesn't have to be boring.

You are READ-ONLY — you never move money, initiate transfers, or handle payments. \
If asked to do so, decline clearly and explain why.

Note: Full Plaid bank sync, transaction tracking, and automated weekly reports are coming \
in Phase 5. For now, you can advise on money topics, budgeting frameworks, and financial \
habits freely."""


async def run(state: AgentState) -> dict:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model_cheap,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": state["user_message"]},
            ],
            max_tokens=512,
        )
        reply = resp.choices[0].message.content or "I'm Chandler — here to talk money!"
    except Exception as exc:
        logger.warning("Chandler LLM error: {}", exc)
        reply = (
            "I'm Chandler, your finance advisor! 💰 I can help with budgeting, savings, "
            "and spending habits. Full bank sync via Plaid is coming in Phase 5. "
            "What's on your mind financially?"
        )

    # Best-effort Obsidian capture — never blocks the reply
    obsidian_path = await try_obsidian_capture(state["user_message"], "finance")

    return {"reply": reply, "obsidian_path": obsidian_path, "intent": "finance"}
