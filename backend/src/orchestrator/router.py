"""Intent classification using the cheap OpenAI model."""
from __future__ import annotations

from typing import Literal

from loguru import logger
from openai import AsyncOpenAI

from src.config import get_settings

Intent = Literal["knowledge", "health", "finance", "calendar", "general"]

_SYSTEM = """You are an intent classifier for a personal AI assistant.

Classify the user's message into ONE of:
- knowledge: AI news, papers, articles, tools, learning; saving/bookmarking URLs or notes; reading list management (show list, mark as read, delete from list, progress update, remove from list, bookmark, "save in notes", "save this"); on-demand digests; summarizing articles; finding or downloading books including fiction ("help me read Verity", "download atomic habits", follow-ups like "add to my reading list" when discussing a book)
- health: food, eating, workouts, weight, sleep, body metrics, groceries, recipes
- finance: spending, budgets, transactions, subscriptions, savings, banking
- calendar: scheduling events ("schedule", "book", "put on my calendar"); viewing agenda ("what's on today", "my schedule"); person/contact notes ("what do I know about X", "add X to my contacts", "X works at Y", "met X at", "update X's role", "who is X", "tell me about X"); anything involving a named person, meeting, or relationship
- general: anything else

Respond with EXACTLY ONE WORD. No punctuation, no explanation."""


async def classify_intent(message: str) -> Intent:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model_cheap,
            max_tokens=10,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": message},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip().lower()
    except Exception as e:
        logger.warning("Intent classification failed: {}", e)
        return "general"

    if raw in {"knowledge", "health", "finance", "calendar", "general"}:
        return raw  # type: ignore[return-value]
    return "general"
