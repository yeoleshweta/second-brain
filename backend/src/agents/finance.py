"""Finance Agent — Plaid-synced spending analysis.

Stub. To flesh out:
- Daily scheduler: sync transactions from each linked Plaid item
- Categorize with the LLM when Plaid's auto-categorization is ambiguous
- Weekly: write 03-Finance/Weekly/YYYY-WW.md with summary + anomalies
- On query: answer spending questions from the SQLite transactions table

SECURITY: read-only. Never moves money. Never sends payments.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.agents._base import stub_run

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState

SYSTEM_PROMPT = """You are the Finance Agent. You analyze the user's spending using
Plaid-synced data stored locally. You write to 03-Finance/ in Obsidian and answer
questions about their finances. You NEVER initiate transactions or move money — you
only read and analyze."""


async def run(state: "AgentState") -> dict:
    return await stub_run(state, "finance")
