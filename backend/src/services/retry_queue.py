"""Hold a failed Void capture until a later write.

Local file is the queue when Supabase is not configured. The same rows
belong in public.retry_queue once SUPABASE_URL is set (see supabase/schema.sql).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from src.config import get_settings


def _path() -> Path:
    root = Path(get_settings().data_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root / "retry-queue.jsonl"


def enqueue(line: str) -> None:
    row = {"line": line, "at": datetime.now(UTC).isoformat(), "attempts": 0}
    with _path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    logger.info("Queued failed Void capture")


def pending_count() -> int:
    path = _path()
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
