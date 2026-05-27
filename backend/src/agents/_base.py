"""Shared helper used by stub agent implementations."""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.integrations import ObsidianClient

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState


async def stub_run(state: "AgentState", agent_name: str) -> dict:
    async with ObsidianClient() as client:
        path = await client.append_to_inbox(
            f"[{agent_name}] {state['user_message']}",
            source=f"agent:{agent_name}",
        )
    return {
        "reply": f"({agent_name} agent — stub) Captured to `{path}`",
        "obsidian_path": path,
    }
