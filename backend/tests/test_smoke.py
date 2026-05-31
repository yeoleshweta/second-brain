"""Smoke tests — make sure imports work and graph builds."""
from __future__ import annotations


def test_graph_builds() -> None:
    from src.orchestrator.graph import build_graph

    assert build_graph() is not None


def test_agents_have_run() -> None:
    from src.agents import calendar_agent, finance, health, knowledge

    for mod in (knowledge, health, finance, calendar_agent):
        assert hasattr(mod, "run"), f"{mod.__name__} missing run()"
