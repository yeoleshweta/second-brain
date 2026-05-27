"""Knowledge Agent — curates AI news, papers, articles.

Stub. To flesh out:
- On "what's new": call fetch_rss + search_arxiv, summarize with Claude
- On "save this <url>": store to 01-Knowledge/To-Read.md
- Scheduler job at 06:00 daily: build digest, write to 00-Inbox/Daily/.
"""
from __future__ import annotations

from src.agents._base import stub_run
from src.orchestrator.graph import AgentState

SYSTEM_PROMPT = """You are the Knowledge Agent. You curate AI/research news for the user,
save articles they want to read, and write daily digests to their Obsidian vault under
01-Knowledge/. Be concise and skip filler."""


async def run(state: AgentState) -> dict:
    return await stub_run(state, "knowledge")
