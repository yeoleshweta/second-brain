"""Combined morning brief — assembles Chandler's schedule + Ross's picks into one file."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from loguru import logger

from src.integrations.obsidian import ObsidianClient


async def build_combined_brief() -> str:
    """Build and write the unified morning brief. Returns the vault path."""
    from src.agents import calendar_agent, knowledge

    chandler_md, ross_md = await __import__("asyncio").gather(
        calendar_agent.morning_section(),
        knowledge.morning_section(),
    )

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    path = f"00-Inbox/Daily/{today}-Brief.md"

    content = (
        f"# Morning Brief — {today}\n\n"
        f"*Compiled at {now.strftime('%H:%M')}*\n\n"
        f"{chandler_md}\n"
        f"{ross_md}\n"
    )

    try:
        async with ObsidianClient() as c:
            await c.create_note(path, content)
        logger.info("Combined brief written to {}", path)
    except Exception as e:
        logger.error("Combined brief Obsidian write failed: {}", e)
        return ""

    return path
