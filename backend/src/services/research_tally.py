"""Count today's vault writes for the P1 evening tally (not written to Log)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

_LOG_LINE = re.compile(r"^- \d{2}:\d{2}\b")


def count_daily_log_lines(daily_note: Path) -> int:
    """Count append-only log items under ## Log until the next heading."""
    if not daily_note.is_file():
        return 0
    text = daily_note.read_text(encoding="utf-8")
    in_log = False
    n = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_log = stripped.lower() == "## log"
            continue
        if in_log and _LOG_LINE.match(stripped):
            n += 1
    return n


def count_unsorted_for_day(unsorted_dir: Path, day: date) -> int:
    """Count Unsorted files whose names start with YYYY-MM-DD."""
    if not unsorted_dir.is_dir():
        return 0
    prefix = day.isoformat()
    return sum(1 for p in unsorted_dir.iterdir() if p.is_file() and p.name.startswith(prefix))


def tally_for_day(vault: Path, day: date) -> tuple[int, int]:
    daily = vault / "00-Inbox" / "Daily" / f"{day.isoformat()}.md"
    unsorted = vault / "00-Inbox" / "Unsorted"
    return count_daily_log_lines(daily), count_unsorted_for_day(unsorted, day)
