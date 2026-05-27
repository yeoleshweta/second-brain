"""Apple Health import.

How it works:
  iOS app 'Health Auto Export' (paid, ~$5) exports your HealthKit data
  on a schedule as JSON files to iCloud Drive (or Dropbox).

  This module watches HEALTH_EXPORT_DIR for new JSON files, parses them,
  and stores daily metrics in SQLite + writes summaries to Obsidian.

To set up:
  1. Buy 'Health Auto Export' on iOS App Store
  2. Configure it to export to iCloud Drive in a folder you'll point to
  3. Set HEALTH_EXPORT_DIR in .env to that folder
  4. Run the watcher as part of the backend (already wired in scheduler)
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from loguru import logger
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.config import get_settings


def parse_health_export(path: Path) -> dict[str, Any]:
    """Parse a JSON export file from Health Auto Export.

    The schema varies by app version. This is a permissive parser.
    Extend with the actual fields you care about (steps, active_energy,
    heart_rate, weight, sleep).
    """
    raw = json.loads(path.read_text())
    # Health Auto Export wraps data in {"data": {"metrics": [...], "workouts": [...]}}
    data = raw.get("data", raw)
    metrics = data.get("metrics", [])

    parsed: dict[str, Any] = {"metrics": {}, "workouts": data.get("workouts", [])}
    for m in metrics:
        name = m.get("name", "unknown")
        # Most metrics have a list of daily values
        parsed["metrics"][name] = m.get("data", [])
    return parsed


class HealthExportHandler(FileSystemEventHandler):
    def __init__(self, on_new_file) -> None:
        self._callback = on_new_file
        super().__init__()

    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".json"):
            return
        logger.info("New health export detected: {}", event.src_path)
        # Run async callback from sync handler
        asyncio.run(self._callback(Path(event.src_path)))


def start_watcher(callback) -> Observer:
    """Start watching HEALTH_EXPORT_DIR. Returns the Observer (call .stop() to halt)."""
    settings = get_settings()
    if not settings.health_export_dir:
        raise RuntimeError("HEALTH_EXPORT_DIR not set in .env")
    watch_path = Path(settings.health_export_dir)
    watch_path.mkdir(parents=True, exist_ok=True)

    handler = HealthExportHandler(callback)
    observer = Observer()
    observer.schedule(handler, str(watch_path), recursive=False)
    observer.start()
    logger.info("Watching {} for Apple Health exports", watch_path)
    return observer
