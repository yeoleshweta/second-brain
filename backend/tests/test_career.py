"""Career agent (Rachel) — vault reads, routing, no Profile writes."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.career import handle_chat, run
from src.config.settings import get_settings
from src.integrations.obsidian import ObsidianClient
from src.services.career_profile import is_template, load_career_context


@pytest.fixture
def career_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    vault = tmp_path / "vault"
    profile = vault / "Career" / "Profile"
    profile.mkdir(parents=True)
    (vault / "Context").mkdir()
    (profile / "background.md").write_text(
        "# Background\n\nStaff engineer at a payments company.\n",
        encoding="utf-8",
    )
    (profile / "skills.md").write_text(
        "# Skills\n\nPython, FastAPI, systems design.\n",
        encoding="utf-8",
    )
    (profile / "goals.md").write_text("# Goals\n\nStaff+ IC, public writing.\n", encoding="utf-8")
    (profile / "paths.md").write_text("# Paths\n\nPlatform engineering.\n", encoding="utf-8")
    (vault / "Context" / "career.md").write_text(
        "Route job, resume, and interview questions here.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OBSIDIAN_API_KEY", "")
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    get_settings.cache_clear()
    yield vault
    get_settings.cache_clear()


def test_template_detection() -> None:
    assert is_template("---\nstatus: template\n---\n<!-- fill this in -->")
    assert not is_template("# Skills\nPython and FastAPI")


@pytest.mark.asyncio
async def test_list_and_read_profile(career_vault: Path) -> None:
    async with ObsidianClient() as obs:
        names = await obs.list_folder("Career/Profile")
        notes = await obs.read_markdown_folder("Career/Profile")
        body = await obs.read_note("Career/Profile/skills.md")
    assert "skills.md" in names
    assert "Python" in notes["skills.md"]
    assert "FastAPI" in body


@pytest.mark.asyncio
async def test_load_career_context_usable(career_vault: Path) -> None:
    block, usable = await load_career_context()
    assert usable
    assert "Staff engineer" in block
    assert "Platform engineering" in block


@pytest.mark.asyncio
async def test_handle_chat_injects_profile(career_vault: Path) -> None:
    captured: dict = {}

    class _FakeResp:
        class _Choice:
            class _Msg:
                content = "You already have platform depth — lean into Staff+ IC writing."

            message = _Msg()

        choices = [_Choice()]

    async def fake_create(**kwargs):  # type: ignore[no-untyped-def]
        captured["messages"] = kwargs["messages"]
        return _FakeResp()

    fake_client = AsyncMock()
    fake_client.chat.completions.create = fake_create

    with patch("src.agents.career.AsyncOpenAI", return_value=fake_client):
        result = await handle_chat("What should I work on next?")

    system = captured["messages"][0]["content"]
    assert "Staff engineer" in system
    assert "never write" in system.lower() or "CANNOT" in system
    assert result["intent"] == "career"
    assert result["obsidian_path"] is None
    assert "Staff+" in result["reply"]


@pytest.mark.asyncio
async def test_run_does_not_write_profile(career_vault: Path) -> None:
    skills = career_vault / "Career" / "Profile" / "skills.md"
    before = skills.read_text(encoding="utf-8")

    class _FakeResp:
        class _Choice:
            class _Msg:
                content = "ok"

            message = _Msg()

        choices = [_Choice()]

    async def fake_create(**kwargs):  # type: ignore[no-untyped-def]
        return _FakeResp()

    fake_client = AsyncMock()
    fake_client.chat.completions.create = fake_create

    with patch("src.agents.career.AsyncOpenAI", return_value=fake_client):
        await run({"user_message": "update my skills to include Rust", "chat_history": []})

    assert skills.read_text(encoding="utf-8") == before
