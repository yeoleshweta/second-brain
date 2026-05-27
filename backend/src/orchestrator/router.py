"""Intent classification using the cheap Claude model."""
from __future__ import annotations

from typing import Literal

from anthropic import AsyncAnthropic
from loguru import logger

from src.config import get_settings

Intent = Literal["knowledge", "health", "finance", "calendar", "general"]

_SYSTEM = """You are an intent classifier for a personal AI assistant.

Classify the user's message into ONE of:
- knowledge: AI news, papers, articles, tools, learning, "save this"
- health: food, eating, workouts, weight, sleep, body metrics, groceries, recipes
- finance: spending, budgets, transactions, subscriptions, savings, banking
- calendar: meetings, scheduling, reminders, follow-ups, people, networking
- general: anything else

Respond with EXACTLY ONE WORD. No punctuation, no explanation."""


async def classify_intent(message: str) -> Intent:
    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        resp = await client.messages.create(
            model=settings.anthropic_model_cheap,
            max_tokens=10,
            system=_SYSTEM,
            messages=[{"role": "user", "content": message}],
        )
        raw = resp.content[0].text.strip().lower()  # type: ignore[union-attr]
    except Exception as e:
        logger.warning("Intent classification failed: {}", e)
        return "general"

    if raw in {"knowledge", "health", "finance", "calendar", "general"}:
        return raw  # type: ignore[return-value]
    return "general"
