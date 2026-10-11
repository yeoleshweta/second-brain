#!/usr/bin/env python3
"""Print today's Log vs Unsorted counts for the P1 evening tally."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from src.services.research_tally import tally_for_day  # noqa: E402


def _vault_from_env() -> Path:
    env = BACKEND / ".env"
    if not env.is_file():
        raise SystemExit("backend/.env missing")
    for line in env.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        if k.strip() == "OBSIDIAN_VAULT_PATH":
            path = Path(v.strip().strip("'").strip('"'))
            if not path.is_dir():
                raise SystemExit(f"vault not found: {path}")
            return path
    raise SystemExit("OBSIDIAN_VAULT_PATH not set")


def main() -> None:
    day = date.today()
    vault = _vault_from_env()
    log_n, unsorted_n = tally_for_day(vault, day)
    print(f"date: {day.isoformat()}")
    print(f"saved_to_log: {log_n}")
    print(f"landed_in_unsorted: {unsorted_n}")
    print("should_have_saved_but_didnt: (you — scan chat)")


if __name__ == "__main__":
    main()
