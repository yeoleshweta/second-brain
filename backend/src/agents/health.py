"""Health Agent — diet, workouts, weight tracking.

Stub. To flesh out:
- Detect food log messages ("I ate X") → look up nutrition via USDA, append to today's log
- Handle receipt uploads → call receipt_ocr.parse_receipt → write to Groceries/
- Read Apple Health daily summaries and write weekly progress notes
"""
from __future__ import annotations

from src.agents._base import stub_run
from src.orchestrator.graph import AgentState

SYSTEM_PROMPT = """You are the Health Agent. You track the user's diet, workouts, and
weight-loss progress. You're warm but honest. You write to 02-Health/ in their Obsidian
vault and store structured logs in SQLite. You ask clarifying questions when entries
are ambiguous (e.g. portion sizes)."""


async def run(state: AgentState) -> dict:
    # TODO: branch on attachments — if there's an image, treat as receipt
    return await stub_run(state, "health")
