"""Attachment kind inference and document-vs-media routing."""
from __future__ import annotations

from src.integrations.speech import plain_for_speech
from src.orchestrator.graph import _classify_node
from src.services.uploads import has_document_attachment, infer_attachment_kind


def test_infer_audio_and_image() -> None:
    assert infer_attachment_kind({"media_type": "audio/webm", "filename": "v.webm"}) == "audio"
    assert infer_attachment_kind({"media_type": "audio/mp4", "filename": "v.m4a"}) == "audio"
    assert infer_attachment_kind({"media_type": "image/jpeg", "filename": "x.jpg"}) == "image"
    assert infer_attachment_kind({"media_type": "application/pdf", "filename": "a.pdf"}) == "pdf"


def test_document_attachment_detection() -> None:
    assert has_document_attachment([{"media_type": "application/pdf", "filename": "a.pdf"}])
    assert not has_document_attachment([{"media_type": "image/png", "filename": "p.png"}])
    assert not has_document_attachment([{"media_type": "audio/webm", "filename": "v.webm"}])


def test_plain_for_speech_strips_markdown() -> None:
    out = plain_for_speech("**Hello** [site](https://example.com)\n\n# Title")
    assert "**" not in out
    assert "http" not in out
    assert "Hello" in out


async def test_image_plus_meal_text_stays_general() -> None:
    out = await _classify_node(
        {
            "user_message": "I ate this for lunch",
            "attachments": [
                {"file_id": "1", "media_type": "image/jpeg", "filename": "plate.jpg"},
            ],
        }
    )
    assert out["intent"] == "general"


async def test_voice_transcript_stays_general() -> None:
    out = await _classify_node(
        {
            "user_message": "[Voice message]: help me prep my resume for an interview",
            "attachments": [
                {"file_id": "1", "media_type": "audio/webm", "filename": "note.webm"},
            ],
        }
    )
    assert out["intent"] == "general"
