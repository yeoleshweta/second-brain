"""Calendar / Networking Agent.

Stub. To flesh out:
- Daily morning: list today's events + suggested prep notes (from People/)
- "Schedule X with Y on date" → create_event with confirmation
- After meetings: prompt for follow-ups, append to person's People/ note
- Periodic: surface people not contacted in 90+ days
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.agents._base import stub_run

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState

SYSTEM_PROMPT = """You are the Calendar & Networking Agent. You manage the user's
schedule, surface follow-ups, and maintain their relationship notes in 04-People/
in Obsidian. You ALWAYS confirm before creating calendar events or sending invites."""


async def run(state: AgentState) -> dict:
    return await stub_run(state, "calendar")
