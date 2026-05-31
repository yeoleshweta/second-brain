"""Chandler agent tests — intent classification, pending actions, people service."""
from __future__ import annotations

import asyncio
import time
from datetime import date
from pathlib import Path
import tempfile

import pytest

from src.agents.calendar_agent import (
    classify_chandler_intent,
    is_yes_no_or_cancel,
)
from src.services import pending_actions as pa


# ── Intent classification ──────────────────────────────────────────────────────

@pytest.mark.parametrize("msg", [
    "schedule coffee with Sarah Tuesday at 3pm",
    "book a meeting with John tomorrow",
    "set up a call with the team Monday",
    "put on my calendar dentist Friday",
    "create an event for lunch",
    "add a meeting with Bob",
])
def test_schedule_intent(msg: str) -> None:
    assert classify_chandler_intent(msg) == "schedule"


@pytest.mark.parametrize("msg", [
    "what's on today?",
    "today's agenda",
    "what do I have today",
    "what am i doing today",
    "my schedule",
    "agenda",
])
def test_agenda_intent(msg: str) -> None:
    assert classify_chandler_intent(msg) == "agenda"


@pytest.mark.parametrize("msg", [
    "what do I know about Sarah?",
    "info on John Smith",
    "who is Alice?",
    "tell me about Bob",
])
def test_find_person_intent(msg: str) -> None:
    assert classify_chandler_intent(msg) == "find_person"


@pytest.mark.parametrize("msg", [
    "Sarah Wong works at Anthropic",
    "met Alice at Re:Invent",
    "add Bob to my contacts",
])
def test_add_person_intent(msg: str) -> None:
    assert classify_chandler_intent(msg) == "add_person"


@pytest.mark.parametrize("msg", [
    "Sarah is now at OpenAI",
    "update Sarah with new role",
    "John just got promoted",
    "Alice moved to London",
])
def test_update_person_intent(msg: str) -> None:
    assert classify_chandler_intent(msg) == "update_person"


@pytest.mark.parametrize("msg", [
    "hey Chandler what's up",
    "can you help me think about a networking strategy",
    "what do you think about this",
])
def test_chat_intent(msg: str) -> None:
    assert classify_chandler_intent(msg) == "chat"


@pytest.mark.parametrize("msg", ["yes", "y", "yep", "confirm", "do it", "sure", "ok"])
def test_yes_detection(msg: str) -> None:
    assert is_yes_no_or_cancel(msg)


@pytest.mark.parametrize("msg", ["no", "n", "nope", "cancel", "stop", "nah"])
def test_no_detection(msg: str) -> None:
    assert is_yes_no_or_cancel(msg)


@pytest.mark.parametrize("msg", ["maybe later", "tell me more", "schedule coffee"])
def test_ambiguous_not_yes_no(msg: str) -> None:
    assert not is_yes_no_or_cancel(msg)


# ── Pending actions ────────────────────────────────────────────────────────────

def test_pending_set_and_consume() -> None:
    pa.clear_pending()
    pa.set_pending("create_event", {"summary": "Coffee"})
    p = pa.consume_pending()
    assert p is not None
    assert p.kind == "create_event"
    assert p.payload["summary"] == "Coffee"
    # Consumed — next call returns None
    assert pa.consume_pending() is None


def test_pending_ttl_expiry() -> None:
    pa.clear_pending()
    pa.set_pending("create_event", {"summary": "Expired"}, ttl_minutes=0)
    # ttl_minutes=0 means it expired at the moment it was set (or in the past)
    time.sleep(0.05)
    assert pa.peek_pending() is None
    assert pa.consume_pending() is None


def test_pending_peek_does_not_consume() -> None:
    pa.clear_pending()
    pa.set_pending("create_person", {"name": "Alice"})
    p1 = pa.peek_pending()
    p2 = pa.peek_pending()
    assert p1 is not None
    assert p2 is not None
    assert p1.kind == p2.kind
    p3 = pa.consume_pending()
    assert p3 is not None
    assert pa.consume_pending() is None


# ── People service ─────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_vault(tmp_path: Path, monkeypatch) -> Path:
    """Patch settings to point people at a temp directory."""
    people_dir = tmp_path / "04-People"
    people_dir.mkdir(parents=True)

    from src.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "obsidian_vault_path", str(tmp_path))
    return tmp_path


def test_people_create_and_find(tmp_vault: Path) -> None:
    from src.services import people
    path = people.create("Sarah Wong", company="Anthropic", role="Research Engineer")
    assert path.exists()
    matches = people.find("Sarah")
    assert len(matches) == 1
    assert matches[0]["frontmatter"]["name"] == "Sarah Wong"
    assert matches[0]["frontmatter"]["company"] == "Anthropic"


def test_people_update_frontmatter(tmp_vault: Path) -> None:
    from src.services import people
    path = people.create("Bob Smith", role="Engineer")
    people.update_frontmatter(path, {"role": "Staff Engineer", "company": "OpenAI"})
    refreshed = people.find("Bob Smith")
    assert refreshed[0]["frontmatter"]["role"] == "Staff Engineer"
    assert refreshed[0]["frontmatter"]["company"] == "OpenAI"


def test_people_log_interaction(tmp_vault: Path) -> None:
    from src.services import people
    path = people.create("Alice Chen")
    people.log_interaction(path, "Coffee at Sightglass", date(2026, 1, 15))
    refreshed = people.find("Alice")
    body = refreshed[0]["body"]
    assert "## Interactions" in body
    assert "Coffee at Sightglass" in body
    assert refreshed[0]["frontmatter"]["last_interaction"] == "Coffee at Sightglass"


def test_people_days_since_contacted(tmp_vault: Path) -> None:
    from src.services import people
    path = people.create("Old Contact", last_contacted="2024-01-01")
    matches = people.find("Old Contact")
    days = people.days_since_contacted(matches[0])
    assert days is not None and days > 300


def test_people_find_fuzzy(tmp_vault: Path) -> None:
    from src.services import people
    people.create("John Doe", company="Acme")
    people.create("John Smith", company="Wayne Enterprises")
    results = people.find("john")
    assert len(results) == 2


def test_people_find_no_match(tmp_vault: Path) -> None:
    from src.services import people
    results = people.find("Nonexistent Person XYZ")
    assert results == []
