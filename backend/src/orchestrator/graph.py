"""LangGraph orchestrator: classify intent, route to specialist agent."""
from __future__ import annotations

import re
from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph
from loguru import logger

from src.agents import calendar_agent, finance, health, knowledge
from src.orchestrator.router import classify_intent

Intent = Literal["knowledge", "health", "finance", "calendar", "general"]


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


AGENT_NAME_TO_INTENT: dict[str, Intent] = {
    "ross": "knowledge",
    "monica": "health",
    "chandler": "calendar",
    "phoebe": "general",
    "joey": "general",
    "rachel": "general",
}

BROADCAST_REMEMBER_RE = re.compile(
    r"\b(everyone|all)\b.*\b(remember|save|bookmark|note)\b",
    re.IGNORECASE,
)

KEYWORD_INTENT_HINTS: dict[Intent, tuple[str, ...]] = {
    "knowledge": (
        "paper",
        "papers",
        "research",
        "what's new",
        "whats new",
        "ai news",
        "reading list",
        "save in notes",
        "bookmark",
        "help me read",
        "download",
        "add to my reading list",
        "verity",
        "book",
        "stcw",
        "amendment",
        "article",
        "articles",
    ),
    "health": (
        "meal",
        "ate",
        "workout",
        "fitness",
        "calories",
        "nutrition",
        "sleep",
    ),
    "finance": (
        "spend",
        "spent",
        "budget",
        "subscription",
        "money",
        "expense",
        "finance",
    ),
    "calendar": (
        "schedule",
        "calendar",
        "meeting",
        "agenda",
        "what's on today",
        "whats on today",
    ),
    "general": (),
}


def _forced_intent_from_name(message: str) -> Intent | None:
    lowered = message.lower()
    earliest: tuple[int, Intent] | None = None
    for name, intent in AGENT_NAME_TO_INTENT.items():
        idx = lowered.find(name)
        if idx == -1:
            continue
        # Require word boundary-like edges to avoid accidental substring matches.
        before_ok = idx == 0 or not lowered[idx - 1].isalnum()
        after_idx = idx + len(name)
        after_ok = after_idx >= len(lowered) or not lowered[after_idx].isalnum()
        if not (before_ok and after_ok):
            continue
        if earliest is None or idx < earliest[0]:
            earliest = (idx, intent)
    return earliest[1] if earliest else None


def _keyword_fallback_intent(message: str) -> Intent | None:
    lowered = message.lower()
    for intent, words in KEYWORD_INTENT_HINTS.items():
        if any(w in lowered for w in words):
            return intent
    return None


def _last_assistant_intent(history: list[dict]) -> Intent | None:
    for turn in reversed(history):
        if turn.get("role") != "assistant":
            continue
        raw = (turn.get("intent") or "").strip().lower()
        if raw in {"knowledge", "health", "finance", "calendar", "general"}:
            return raw  # type: ignore[return-value]
    return None


def _explicit_switch_intent(message: str) -> Intent | None:
    """User clearly asked for a different specialist."""
    forced = _forced_intent_from_name(message)
    if forced:
        return forced
    lowered = message.lower()
    if any(
        w in lowered
        for w in (
            "calories",
            "workout",
            "meal",
            "nutrition",
            "breakfast",
            "lunch",
            "dinner",
            "macros",
            "protein",
        )
    ):
        return "health"
    if any(
        w in lowered
        for w in ("budget", "subscription", "transaction", "spending", "expense")
    ):
        return "finance"
    if any(w in lowered for w in ("schedule meeting", "calendar", "agenda", "my schedule")):
        return "calendar"
    if any(w in lowered for w in ("inbox", "unread email", "my email", "gmail", "check email")):
        return "calendar"
    return None


def _apply_session_intent_sticky(
    message: str,
    history: list[dict],
    classified: Intent,
) -> Intent:
    """Keep follow-ups with the same agent unless the user switches explicitly."""
    prior = _last_assistant_intent(history)
    if not prior:
        return classified
    explicit = _explicit_switch_intent(message)
    if explicit and explicit != prior:
        return explicit
    if prior == "knowledge" and classified in {"general", "health"}:
        return "knowledge"
    if prior in {"health", "finance", "calendar"} and classified == "general":
        return prior
    return classified


async def _classify_node(state: AgentState) -> dict:
    message = state["user_message"]
    history = state.get("chat_history") or []

    # Any attachment → Ross (save to reading list + Obsidian vault).
    if state.get("attachments"):
        logger.info("Attachment present, routing to knowledge")
        return {"intent": "knowledge"}

    if BROADCAST_REMEMBER_RE.search(message):
        # Route "everyone/all remember this ..." through Ross save flow so memory is captured once.
        logger.info("Broadcast remember detected; routing to knowledge save flow")
        return {"intent": "knowledge", "user_message": f"save in notes {message}"}

    forced_intent = _forced_intent_from_name(message)
    if forced_intent:
        logger.info("Name override detected; routing to {}", forced_intent)
        return {"intent": forced_intent}

    intent = await classify_intent(message)
    logger.info("Classified intent={}", intent)
    if intent == "general":
        fallback_intent = _keyword_fallback_intent(message)
        if fallback_intent and fallback_intent != "general":
            logger.info("Keyword fallback override: general -> {}", fallback_intent)
            intent = fallback_intent
    intent = _apply_session_intent_sticky(message, history, intent)
    logger.info("Final routed intent={}", intent)
    return {"intent": intent}


def _route(state: AgentState) -> str:
    return state.get("intent", "general")


async def _general_node(state: AgentState) -> dict:
    """Phoebe — general chat, wellness, ideas. Pure conversation, no Obsidian required."""
    from openai import AsyncOpenAI

    from src.config import get_settings

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    system = (
        "You are Phoebe, a warm and imaginative AI friend in the user's personal second-brain app. "
        "You handle general conversation, offer creative ideas, wellbeing tips, meditation prompts, "
        "and life inspiration. You're upbeat, a little quirky, and genuinely caring. "
        "Keep replies concise and conversational — 1-3 short paragraphs at most. "
        "Never pretend to have memory of past conversations unless context is provided."
    )
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model_cheap,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": state["user_message"]},
            ],
            max_tokens=512,
        )
        reply = resp.choices[0].message.content or "I'm here! What's on your mind?"
    except Exception as exc:
        logger.warning("Phoebe LLM error: {}", exc)
        reply = "Hey! I'm Phoebe — here for general chat, ideas, and good vibes. What's on your mind? 🌙"

    return {"reply": reply, "obsidian_path": None, "intent": "general"}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("classify", _classify_node)
    graph.add_node("knowledge", knowledge.run)
    graph.add_node("health", health.run)
    graph.add_node("finance", finance.run)
    graph.add_node("calendar", calendar_agent.run)
    graph.add_node("general", _general_node)
    graph.set_entry_point("classify")
    graph.add_conditional_edges(
        "classify",
        _route,
        {
            "knowledge": "knowledge",
            "health": "health",
            "finance": "finance",
            "calendar": "calendar",
            "general": "general",
        },
    )
    for node in ("knowledge", "health", "finance", "calendar", "general"):
        graph.add_edge(node, END)
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
        from src.storage import get_session
        from src.services import chat_history as chat_store

        with next(get_session()) as db:
            history = chat_store.recent_history(db, session_id, limit=20)

    result = await APP.ainvoke(
        {
            "user_message": message,
            "attachments": attachments or [],
            "chat_history": history,
        }
    )
    return result  # type: ignore[return-value]
