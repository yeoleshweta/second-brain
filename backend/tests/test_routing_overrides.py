"""Chat routing is one-bot — no Friends / specialist classification."""
from __future__ import annotations

from src.orchestrator.graph import _classify_node


async def test_classify_always_general_even_with_pdf() -> None:
    out = await _classify_node(
        {
            "user_message": "",
            "attachments": [{"file_id": "1", "media_type": "application/pdf"}],
        }
    )
    assert out["intent"] == "general"


async def test_classify_ignores_specialist_keywords() -> None:
    for msg in (
        "any new research papers for me",
        "I spent 40 dollars yesterday",
        "I had a workout and tracked calories",
        "prep my resume for a staff interview",
        "everyone remember this: project X",
    ):
        out = await _classify_node({"user_message": msg})
        assert out["intent"] == "general"
