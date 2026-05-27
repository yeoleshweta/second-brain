"""LangGraph orchestrator: classify intent, route to specialist agent."""
from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph
from loguru import logger

from src.agents import calendar_agent, finance, health, knowledge
from src.orchestrator.router import classify_intent

Intent = Literal["knowledge", "health", "finance", "calendar", "general"]


class AgentState(TypedDict, total=False):
    user_message: str
    attachments: list[dict]  # [{type, path|data, media_type}]
    intent: Intent
    reply: str
    obsidian_path: str | None
    metadata: dict


async def _classify_node(state: AgentState) -> dict:
    # If there's an attachment (e.g., receipt image), bias toward health
    if state.get("attachments"):
        intent: Intent = "health"
        logger.info("Attachment present, routing to health")
    else:
        intent = await classify_intent(state["user_message"])
        logger.info("Classified intent={}", intent)
    return {"intent": intent}


def _route(state: AgentState) -> str:
    return state.get("intent", "general")


async def _general_node(state: AgentState) -> dict:
    from src.agents._base import stub_run
    return await stub_run(state, "general")


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
    message: str, attachments: list[dict] | None = None
) -> AgentState:
    result = await APP.ainvoke(
        {"user_message": message, "attachments": attachments or []}
    )
    return result  # type: ignore[return-value]
