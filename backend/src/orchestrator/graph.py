"""LangGraph orchestrator: one bot → one vault daily note.

Chat never classifies into leftover Friends specialists. Those agent files
remain on disk unused by this graph.
"""
from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph
from loguru import logger

from src.agents.second_brain import run as second_brain_run

Intent = Literal["knowledge", "health", "finance", "calendar", "career", "general"]


class AgentState(TypedDict, total=False):
    user_message: str
    attachments: list[dict]  # [{type, path|data, media_type}]
    chat_history: list[dict]  # [{role, content}] recent turns for follow-ups
    intent: Intent
    reply: str
    digest_items: list[dict]
    suggest_items: list[dict]
    book_items: list[dict]
    obsidian_path: str | None
    metadata: dict


async def _classify_node(state: AgentState) -> dict:
    """Chat is one bot. Always general — no specialist / Friends routing."""
    del state
    return {"intent": "general"}


async def _general_node(state: AgentState) -> dict:
    return await second_brain_run(state)


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("classify", _classify_node)
    graph.add_node("general", _general_node)
    graph.set_entry_point("classify")
    graph.add_edge("classify", "general")
    graph.add_edge("general", END)
    return graph.compile()


APP = build_graph()


async def handle_message(
    message: str,
    attachments: list[dict] | None = None,
    chat_history: list[dict] | None = None,
    *,
    session_id: str | None = None,
) -> AgentState:
    history = list(chat_history or [])
    if session_id and not history:
        from src.services import chat_history as chat_store
        from src.storage import get_session

        with next(get_session()) as db:
            history = chat_store.recent_history(db, session_id, limit=20)

    from src.agents._base import is_inbox_thought_dump, try_obsidian_capture
    from src.services.media_ingest import enrich_user_message

    attachments = attachments or []
    enriched = await enrich_user_message(message, attachments)
    try:
        result = await APP.ainvoke(
            {
                "user_message": enriched,
                "attachments": attachments,
                "chat_history": history,
            }
        )
    except Exception as exc:
        from src.integrations.openai_status import public_openai_error

        logger.warning("Orchestrator failed: {}", type(exc).__name__)
        result = {
            "user_message": enriched,
            "attachments": attachments,
            "chat_history": history,
            "reply": public_openai_error(exc),
            "intent": "general",
            "obsidian_path": None,
        }

    # Thought-dumps use the v1 contract: 00-Inbox/Daily/ under ## Log (or Unsorted).
    if not result.get("obsidian_path") and is_inbox_thought_dump(enriched):
        path = await try_obsidian_capture(enriched, "general")
        if path:
            result["obsidian_path"] = path
            reply = (result.get("reply") or "").rstrip()
            if path not in reply:
                result["reply"] = f"{reply}\n\nSaved to `{path}`."

    result["user_message"] = enriched
    result["intent"] = "general"
    return result  # type: ignore[return-value]
