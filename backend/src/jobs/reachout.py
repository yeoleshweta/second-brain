"""Sunday reach-out job — surfaces stale contacts (90+ days since last contact)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from loguru import logger

from src.integrations.obsidian import ObsidianClient
from src.services import people


STALE_DAYS = 90
MAX_CONTACTS = 5


async def build_reachout_section() -> str:
    """Scan 04-People/ and return a '## 🤝 Reach out this week' section."""
    all_people = people.list_all()
    stale = []

    for person in all_people:
        days = people.days_since_contacted(person)
        # days is None means never contacted — treat as very old
        effective_days = days if days is not None else 9999
        if effective_days >= STALE_DAYS:
            stale.append((effective_days, person))

    stale.sort(key=lambda x: -x[0])  # oldest first
    top = stale[:MAX_CONTACTS]

    if not top:
        return ""

    lines = ["## 🤝 Reach out this week\n"]
    for days, person in top:
        fm = person["frontmatter"]
        name = fm.get("name") or Path(person["filename"]).stem.replace("-", " ")
        last_str = fm.get("last_interaction") or "no recorded interaction"
        days_label = f"{days} days ago" if days < 9999 else "never"
        lines.append(f"- **{name}** — last contacted {days_label}. _{last_str}_")

    return "\n".join(lines) + "\n"


async def append_reachout_to_brief() -> None:
    """Build the reach-out section and append it to today's combined brief."""
    section = await build_reachout_section()
    if not section:
        logger.info("Reach-out job: no stale contacts found")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    brief_path = f"00-Inbox/Daily/{today}-Brief.md"

    try:
        async with ObsidianClient() as c:
            try:
                existing = await c.get_note(brief_path)
            except Exception:
                # Brief doesn't exist yet — build it first
                from src.jobs.combined_brief import build_combined_brief
                await build_combined_brief()
                existing = await c.get_note(brief_path)

            updated = existing.rstrip() + "\n\n" + section
            await c.create_note(brief_path, updated)

        logger.info("Reach-out section appended to {}", brief_path)
    except Exception as e:
        logger.error("Reach-out append failed: {}", e)
