"""Ross follow-up intent and book context resolution."""
from __future__ import annotations

from src.agents.knowledge import (
    classify_sub_intent,
    is_list_command,
    _resolve_book_query,
)


def test_list_command_not_triggered_by_download_add_request() -> None:
    msg = "okay help me download and add to my reading list"
    assert is_list_command(msg) is False


def test_help_me_read_verity_is_download_book() -> None:
    assert classify_sub_intent("can you help me read verity?") == "download_book"


def test_follow_up_download_uses_history_for_title() -> None:
    history = [
        {"role": "user", "content": "can you help me read verity?"},
        {
            "role": "assistant",
            "content": "Absolutely! 'Verity' by Colleen Hoover is quite a gripping read.",
        },
    ]
    msg = "okay help me download and add to my reading list"
    assert classify_sub_intent(msg, history=history) == "download_book"
    assert _resolve_book_query(msg, history).lower() == "verity"


def test_show_reading_list_still_works() -> None:
    assert is_list_command("show my reading list") is True
    assert classify_sub_intent("show my reading list") == "list"
