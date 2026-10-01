"""Leftover unused classifier — chat no longer routes by specialist.

Kept so older imports do not break. Always returns general.
"""
from __future__ import annotations

from typing import Literal

from loguru import logger

Intent = Literal["knowledge", "health", "finance", "calendar", "career", "general"]


async def classify_intent(message: str) -> Intent:
    """Unused by the live chat graph. Always general."""
    del message
    logger.debug("classify_intent is unused; chat is one-bot")
    return "general"
