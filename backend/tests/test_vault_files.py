"""Vault file capture tests."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.services import vault_files as vf


@pytest.fixture
def vault_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    from src.config.settings import get_settings

    get_settings.cache_clear()
    yield vault
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_store_file_in_vault(vault_tmp: Path, tmp_path: Path) -> None:
    src = tmp_path / "notes.txt"
    src.write_text("hello vault", encoding="utf-8")

    async def fake_create_note(path: str, content: str) -> None:
        dest = vault_tmp / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    mock_obs = AsyncMock()
    mock_obs.create_note = fake_create_note
    mock_obs.__aenter__ = AsyncMock(return_value=mock_obs)
    mock_obs.__aexit__ = AsyncMock(return_value=None)

    with patch("src.services.vault_files.ObsidianClient", return_value=mock_obs):
        rel, note = await vf.store_file_in_vault(src, title="Test note", summary="A test")

    assert (vault_tmp / rel).exists()
    assert (vault_tmp / note).exists()
    assert rel in (vault_tmp / note).read_text()
