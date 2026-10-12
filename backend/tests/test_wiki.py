from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.config.settings import get_settings
from src.services import wiki


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "vault"
    (root / "Inbox").mkdir(parents=True)
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(root))
    monkeypatch.setenv("GITHUB_VAULT_REPO", "")
    monkeypatch.setenv("GITHUB_TOKEN", "")
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_ingest_stays_in_inbox(vault: Path) -> None:
    path = await wiki.ingest_raw(title="Walk", body="30 min walk", source="chat")
    assert path.startswith("Inbox/")
    text = (vault / path).read_text(encoding="utf-8")
    assert "30 min walk" in text
    assert "status: inbox" in text
    assert not list((vault / "Notes").glob("*.md")) if (vault / "Notes").exists() else True


@pytest.mark.asyncio
async def test_approve_files_only_after_proposal(vault: Path) -> None:
    path = await wiki.ingest_raw(title="Mentorship", body="Tany and Shweta met.", source="meeting")
    with pytest.raises(ValueError, match="no proposal"):
        await wiki.approve(path)

    payload = {
        "summary": "Mentorship intro.",
        "key_concepts": ["mentorship", "UX"],
        "people": ["Tany", "Shweta"],
        "action_items": ["Share portfolio"],
        "related_topics": ["career"],
        "destination_folder": "Projects",
        "destination_title": "Mentorship Tany Shweta",
        "processed_content": "## Mentorship\n\nMet [[Tany]] about UX.",
    }
    with patch("src.integrations.claude.complete", AsyncMock(return_value=json.dumps(payload))):
        proposed = await wiki.propose(path)
    assert proposed["status"] == "proposed"
    assert proposed["destination"].startswith("Projects/")

    result = await wiki.approve(path)
    dest = vault / result["destination"]
    assert dest.is_file()
    assert "[[Tany]]" in dest.read_text(encoding="utf-8")
    inbox = (vault / path).read_text(encoding="utf-8")
    assert "status: processed" in inbox


@pytest.mark.asyncio
async def test_reject_does_not_file(vault: Path) -> None:
    path = await wiki.ingest_raw(title="Skip me", body="noise", source="chat")
    await wiki.reject(path)
    text = (vault / path).read_text(encoding="utf-8")
    assert "status: rejected" in text
    pending = await wiki.list_pending()
    assert pending == []


def test_wiki_destination_guard() -> None:
    with pytest.raises(PermissionError):
        wiki._assert_wiki_destination("01-Knowledge/Notes/x.md")
    with pytest.raises(PermissionError):
        wiki._assert_wiki_destination("Career/Profile/x.md")
    wiki._assert_wiki_destination("Notes/foo.md")
    wiki._assert_wiki_destination("People/Tany.md")
