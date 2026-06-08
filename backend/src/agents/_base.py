"""Shared helpers for agent implementations."""
from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState


async def try_obsidian_capture(message: str, agent_name: str) -> str | None:
    """Best-effort Obsidian inbox capture — never raises, returns path or None."""
    try:
        from src.integrations import ObsidianClient
        async with ObsidianClient() as client:
            path = await client.append_to_inbox(
                f"[{agent_name}] {message}",
                source=f"agent:{agent_name}",
            )
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
        "reply": f"({agent_name} agent) Got it — Obsidian isn't running so I couldn't save this, but I heard you.",
        "obsidian_path": None,
    }
