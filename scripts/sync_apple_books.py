#!/usr/bin/env python3
"""Sync Apple Books library → Second Brain cloud API.

Run manually:
    python3 scripts/sync_apple_books.py

Or let the LaunchAgent run it every 2 hours automatically.
Requires: SECOND_BRAIN_API_URL and SECOND_BRAIN_API_TOKEN env vars
(set them in ~/.zshenv or pass on the command line).
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────────────────────

BOOKS_DB = Path.home() / (
    "Library/Containers/com.apple.iBooksX/Data/Documents/BKLibrary/"
    "BKLibrary-1-091020131601.sqlite"
)

API_URL   = os.environ.get("SECOND_BRAIN_API_URL", "").rstrip("/")
API_TOKEN = os.environ.get("SECOND_BRAIN_API_TOKEN", "")

# Apple Books epoch starts 2001-01-01 (CoreData timestamp)
_APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


def _apple_ts_to_iso(ts: float | None) -> str | None:
    if not ts:
        return None
    try:
        dt = _APPLE_EPOCH + __import__("datetime").timedelta(seconds=float(ts))
        return dt.isoformat()
    except Exception:
        return None


# ── Read Apple Books ──────────────────────────────────────────────────────────

def read_library() -> list[dict]:
    if not BOOKS_DB.exists():
        print(f"ERROR: Apple Books database not found at {BOOKS_DB}", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(f"file:{BOOKS_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT
            ZASSETID,
            ZTITLE,
            ZAUTHOR,
            ZGENRE,
            ZREADINGPROGRESS,
            ZBOOKHIGHWATERMARKPROGRESS,
            ZISFINISHED,
            ZLASTOPENDATE,
            ZDATEFINISHED,
            ZPURCHASEDATE,
            ZPAGECOUNT,
            ZRATING
        FROM ZBKLIBRARYASSET
        WHERE ZTITLE IS NOT NULL
          AND ZISSAMPLE = 0
          AND ZISHIDDEN = 0
        ORDER BY ZLASTOPENDATE DESC NULLS LAST
    """)

    books = []
    for row in cur.fetchall():
        asset_id  = str(row["ZASSETID"])
        progress  = float(row["ZREADINGPROGRESS"] or 0)
        hwm       = float(row["ZBOOKHIGHWATERMARKPROGRESS"] or 0)
        is_done   = bool(row["ZISFINISHED"])

        # Determine status
        if is_done or progress >= 0.99:
            status = "finished"
        elif progress > 0.01 or hwm > 0.01:
            status = "reading"
        else:
            status = "unread"

        books.append({
            "apple_books_id": asset_id,
            "title":          row["ZTITLE"] or "Untitled",
            "author":         row["ZAUTHOR"] or "Unknown",
            "genre":          row["ZGENRE"],
            "progress":       round(max(progress, hwm) * 100),  # 0-100
            "status":         status,
            "page_count":     row["ZPAGECOUNT"],
            "rating":         row["ZRATING"],
            "last_opened_at": _apple_ts_to_iso(row["ZLASTOPENDATE"]),
            "finished_at":    _apple_ts_to_iso(row["ZDATEFINISHED"]),
            "purchased_at":   _apple_ts_to_iso(row["ZPURCHASEDATE"]),
        })

    con.close()
    return books


# ── Push to API ───────────────────────────────────────────────────────────────

def push_to_api(books: list[dict]) -> dict:
    if not API_URL:
        print("ERROR: SECOND_BRAIN_API_URL not set.", file=sys.stderr)
        print("  export SECOND_BRAIN_API_URL=https://your-app.onrender.com", file=sys.stderr)
        sys.exit(1)
    if not API_TOKEN:
        print("ERROR: SECOND_BRAIN_API_TOKEN not set.", file=sys.stderr)
        sys.exit(1)

    payload = json.dumps({"books": books}).encode()
    req = urllib.request.Request(
        f"{API_URL}/api/reading/apple-books/sync",
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {API_TOKEN}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"ERROR {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] Reading Apple Books library…")
    books = read_library()
    print(f"  Found {len(books)} books")

    reading  = [b for b in books if b["status"] == "reading"]
    finished = [b for b in books if b["status"] == "finished"]
    unread   = [b for b in books if b["status"] == "unread"]
    print(f"  Reading: {len(reading)}  Finished: {len(finished)}  Unread: {len(unread)}")

    print(f"  Syncing to {API_URL}…")
    result = push_to_api(books)
    print(f"  Done: {result}")


if __name__ == "__main__":
    main()
