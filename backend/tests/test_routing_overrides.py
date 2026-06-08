from __future__ import annotations

from src.orchestrator.graph import (
    BROADCAST_REMEMBER_RE,
    _classify_node,
    _forced_intent_from_name,
    _keyword_fallback_intent,
)


def test_forced_intent_from_agent_name() -> None:
    assert _forced_intent_from_name("Ross show me new papers") == "knowledge"
    assert _forced_intent_from_name("Monica I had eggs for breakfast") == "health"
    assert _forced_intent_from_name("Chandler what's on my calendar today") == "calendar"
    assert _forced_intent_from_name("Phoebe what should I do this weekend?") == "general"


def test_forced_intent_uses_first_mentioned_name() -> None:
    # If multiple names appear, first mention wins.
    assert _forced_intent_from_name("Ross and Chandler, let's start with this") == "knowledge"
    assert _forced_intent_from_name("Chandler then Ross: schedule a meeting") == "calendar"


def test_broadcast_remember_regex() -> None:
    assert BROADCAST_REMEMBER_RE.search("everyone remember this: project X")
    assert BROADCAST_REMEMBER_RE.search("all save this note for later")
    assert not BROADCAST_REMEMBER_RE.search("everyone hello there")


def test_keyword_fallback_intent() -> None:
    assert _keyword_fallback_intent("any new research papers for me") == "knowledge"
    assert _keyword_fallback_intent("I spent 40 dollars yesterday") == "finance"
    assert _keyword_fallback_intent("I had a workout and tracked calories") == "health"


async def test_attachment_pdf_routes_to_knowledge() -> None:
    out = await _classify_node(
        {
            "user_message": "",
            "attachments": [{"file_id": "1", "media_type": "application/pdf"}],
        }
    )
    assert out["intent"] == "knowledge"
