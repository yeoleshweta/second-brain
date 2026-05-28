from __future__ import annotations

import os

import pytest

from src.agents.knowledge import build_daily_brief, classify_sub_intent


def test_classify_sub_intent_save_url() -> None:
    assert classify_sub_intent("save this https://example.com") == "save_url"


def test_classify_sub_intent_digest_now() -> None:
    assert classify_sub_intent("what's new in AI today?") == "digest_now"


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration checks.",
)
@pytest.mark.asyncio
async def test_build_daily_brief_integration() -> None:
    path = await build_daily_brief()
    assert path.endswith("-AI-Brief.md")
