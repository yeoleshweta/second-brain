"""Knowledge agent unit tests — intent detection and sub-intent classification."""
from __future__ import annotations

import pytest

from src.agents.knowledge import (
    classify_sub_intent,
    is_delete_command,
    is_digest_command,
    is_list_command,
    is_mark_command,
    is_practice_log_command,
    is_practice_status_command,
    is_progress_command,
    is_query_command,
    is_save_command,
    is_suggest_command,
    is_summarize_command,
)

# ── save command ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("msg", [
    "save in notes https://arxiv.org/abs/2312.00752",
    "save this https://example.com",
    "save it for later",
    "bookmark this article",
    "add to reading list",
    "remember this",
    "file this away",
    "save to notes: interesting thread",
])
def test_is_save_command_true(msg):
    assert is_save_command(msg) is True


@pytest.mark.parametrize("msg", [
    "save me from this meeting",
    "saved it already",
    "what did you save?",
    "what's new in AI?",
    "hey",
])
def test_is_save_command_false(msg):
    assert is_save_command(msg) is False


# ── list command ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("msg", [
    "show my reading list",
    "what's in my reading list",
    "reading list",
    "show reading list",
])
def test_is_list_command(msg):
    assert is_list_command(msg) is True


# ── mark as read ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("msg,expected_target", [
    ("mark Mamba as read", "Mamba"),
    ("finished reading Mamba paper", "Mamba paper"),
    ("i just finished Mamba", "Mamba"),
])
def test_is_mark_command(msg, expected_target):
    ok, target = is_mark_command(msg)
    assert ok is True
    assert expected_target.lower() in target.lower()


def test_is_mark_command_false():
    ok, _ = is_mark_command("what's new in AI?")
    assert ok is False


# ── progress command ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("msg,pct,title_fragment", [
    ("50% Mamba", 50, "Mamba"),
    ("I'm 75% done with the attention paper", 75, "attention paper"),
])
def test_is_progress_command(msg, pct, title_fragment):
    ok, got_pct, target = is_progress_command(msg)
    assert ok is True
    assert got_pct == pct
    assert title_fragment.lower() in target.lower()


def test_is_progress_command_false():
    ok, _, _ = is_progress_command("show reading list")
    assert ok is False


# ── delete command ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("msg,title_fragment", [
    ("delete Mamba from my list", "Mamba"),
    ("remove Mamba from list", "Mamba"),
])
def test_is_delete_command(msg, title_fragment):
    ok, target = is_delete_command(msg)
    assert ok is True
    assert title_fragment.lower() in target.lower()


def test_is_delete_command_false():
    ok, _ = is_delete_command("what's new?")
    assert ok is False


# ── digest command ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("msg", [
    "what's new in AI?",
    "any new papers?",
    "latest AI news",
    "new papers today",
    "whats new",
])
def test_is_digest_command(msg):
    assert is_digest_command(msg) is True


# ── summarize command ──────────────────────────────────────────────────────────

def test_is_summarize_command():
    assert is_summarize_command("summarize https://arxiv.org/abs/2312.00752") is True
    assert is_summarize_command("tldr https://example.com/paper") is True
    assert is_summarize_command("what does this say https://x.com/article") is True
    # No URL → False
    assert is_summarize_command("summarize transformers for me") is False


def test_query_and_suggest_detection():
    ok, topic = is_query_command("what do I know about mamba")
    assert ok is True
    assert topic.lower() == "mamba"
    suggest_ok, mins = is_suggest_command("suggest something for a 15 min read")
    assert suggest_ok is True
    assert mins == 15


def test_practice_detection():
    ok, skill, mins = is_practice_log_command("practiced guitar for 45 min")
    assert ok is True
    assert skill == "guitar"
    assert mins == 45
    assert is_practice_status_command("how's my practice going") is True


def test_sub_intent_classification_priority():
    assert classify_sub_intent("stop nagging") == "pause_nudges"
    assert classify_sub_intent("set reading goal to 20 min") == "set_reading_goal"
    assert classify_sub_intent("clear my reading list") == "clear_list"
    assert classify_sub_intent("confirm clear all") == "confirm_clear_list"
    assert classify_sub_intent("save me from this meeting") == "chat"


# ── integration: build_morning_brief ──────────────────────────────────────────

@pytest.mark.integration
async def test_build_morning_brief_writes_file():
    """Integration test — requires Obsidian running and real API keys."""
    from src.agents.knowledge import build_morning_brief

    path = await build_morning_brief()
    assert path, "Expected a non-empty vault path"
    assert "Ross" in path or "Daily" in path
