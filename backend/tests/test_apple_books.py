"""Apple Books MCP routing and handler tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.knowledge import classify_sub_intent, is_apple_books_command
from src.integrations.apple_books import handle_apple_books_request


def test_apple_books_intent_detection() -> None:
    assert is_apple_books_command("what am I reading in Apple Books?")
    assert classify_sub_intent("my recent highlights") == "apple_books"
    assert classify_sub_intent("library stats") == "apple_books"


@pytest.mark.asyncio
async def test_handle_apple_books_in_progress() -> None:
    with patch(
        "src.integrations.apple_books.books_in_progress",
        new=AsyncMock(return_value="[1] Dune — 42%"),
    ), patch(
        "src.integrations.apple_books.recently_read",
        new=AsyncMock(return_value="[2] Foundation"),
    ):
        result = await handle_apple_books_request("what am I reading?")
    assert "Currently in Apple Books" in result["reply"]
    assert "Dune" in result["reply"]


@pytest.mark.asyncio
async def test_handle_apple_books_highlights() -> None:
    with patch(
        "src.integrations.apple_books.recent_highlights",
        new=AsyncMock(return_value="- highlight one"),
    ):
        result = await handle_apple_books_request("show my recent highlights")
    assert "Recent Apple Books highlights" in result["reply"]
    assert "highlight one" in result["reply"]
