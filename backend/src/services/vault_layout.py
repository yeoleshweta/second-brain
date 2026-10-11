"""Ensure the v1 vault tree exists (local Mac or cloud volume)."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

V1_DIRS = (
    "00-Inbox/Daily",
    "00-Inbox/Unsorted",
    "01-Knowledge/Notes",
    "01-Knowledge/Sources",
    "01-Knowledge/MOCs",
    "02-Health/Logs",
    "02-Health/Reviews",
    "03-Finance/Logs",
    "03-Finance/Reviews",
    "04-People",
    "05-Calendar",
    "99-System/Templates",
    "99-System/Schemas",
    "99-System/Logs",
)

V2_DIRS = (
    "Inbox",
    "Notes",
    "People",
    "Projects",
    "Concepts",
    "Briefings",
    "Templates",
)

_DAILY_TEMPLATE = """---
type: daily
date: {{date}}
created: {{date}}T00:00
mood:
energy:
---

# {{date}}

## Log
<!-- bot appends here, newest at bottom -->

## Notes
<!-- your own free writing -->

## Review
- [ ] Triage captures
"""


def ensure_v1_tree(vault: Path | None) -> None:
    if vault is None:
        return
    root = Path(vault)
    root.mkdir(parents=True, exist_ok=True)
    for rel in (*V1_DIRS, *V2_DIRS):
        (root / rel).mkdir(parents=True, exist_ok=True)
    tpl = root / "99-System" / "Templates" / "tpl-daily.md"
    if not tpl.is_file():
        tpl.write_text(_DAILY_TEMPLATE, encoding="utf-8")
        logger.info("Seeded {}", tpl)
