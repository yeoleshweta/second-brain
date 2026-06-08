"""Obsidian integration — dual-mode: REST API (local Mac) or direct filesystem (cloud).

Mode is chosen automatically:
  - If OBSIDIAN_API_KEY is set → use Local REST API plugin (Mac/local)
  - Otherwise → write markdown files directly to OBSIDIAN_VAULT_PATH

This makes the same code work both on your Mac (where Obsidian REST plugin runs)
and in a cloud deployment (where we just write .md files to a mounted volume,
and Obsidian Sync / iCloud keeps the vault in sync with your Mac).
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.config import get_settings


class _RestBackend:
    """Calls the Obsidian Local REST API plugin (https://127.0.0.1:27124)."""

    def __init__(self, api_key: str, base_url: str) -> None:
        import httpx

        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15.0,
            verify=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get(self, path: str) -> str:
        resp = await self._client.get(f"/vault/{path}")
        resp.raise_for_status()
        return resp.text

    async def put(self, path: str, content: str) -> None:
        resp = await self._client.put(
            f"/vault/{path}",
            content=content.encode("utf-8"),
            headers={"Content-Type": "text/markdown"},
        )
        resp.raise_for_status()

    async def append(self, path: str, content: str) -> None:
        resp = await self._client.post(
            f"/vault/{path}",
            content=content.encode("utf-8"),
            headers={"Content-Type": "text/markdown"},
        )
        resp.raise_for_status()


class _FileBackend:
    """Writes markdown files directly to the vault directory on disk."""

    def __init__(self, vault_path: Path) -> None:
        self._root = vault_path

    async def close(self) -> None:
        pass

    def _resolve(self, path: str) -> Path:
        full = self._root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        return full

    async def get(self, path: str) -> str:
        return await asyncio.to_thread(self._resolve(path).read_text, "utf-8")

    async def put(self, path: str, content: str) -> None:
        dest = self._resolve(path)
        await asyncio.to_thread(dest.write_text, content, "utf-8")
        logger.debug("Vault write (file) → {}", dest)

    async def append(self, path: str, content: str) -> None:
        dest = self._resolve(path)

        def _append() -> None:
            with dest.open("a", encoding="utf-8") as f:
                f.write(content)

        await asyncio.to_thread(_append)
        logger.debug("Vault append (file) → {}", dest)


def _make_backend(_rest=None, _file=None):  # type: ignore[no-untyped-def]
    """Build the right backend from settings. Cached after first call."""
    settings = get_settings()
    if settings.obsidian_api_key:
        logger.debug("ObsidianClient: using REST API at {}", settings.obsidian_base_url)
        return _RestBackend(settings.obsidian_api_key, settings.obsidian_base_url)
    if settings.obsidian_vault_path:
        vault = Path(settings.obsidian_vault_path)
        if not vault.exists():
            vault.mkdir(parents=True, exist_ok=True)
        logger.debug("ObsidianClient: using filesystem at {}", vault)
        return _FileBackend(vault)
    raise RuntimeError(
        "Obsidian not configured: set OBSIDIAN_API_KEY (local) or OBSIDIAN_VAULT_PATH (cloud/file)."
    )


class ObsidianClient:
    """Async context manager that writes to your Obsidian vault.

    Works in two modes automatically:
      • Mac/local: uses the Local REST API plugin (OBSIDIAN_API_KEY required)
      • Cloud/CI:  writes .md files directly to OBSIDIAN_VAULT_PATH
    """

    def __init__(self) -> None:
        self._backend = _make_backend()

    async def close(self) -> None:
        await self._backend.close()

    async def __aenter__(self) -> ObsidianClient:
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    async def get_note(self, path: str) -> str:
        return await self._backend.get(path)

    async def create_note(self, path: str, content: str) -> None:
        logger.info("Obsidian create {}", path)
        await self._backend.put(path, content)

    async def append_to_note(self, path: str, content: str) -> None:
        logger.info("Obsidian append {}", path)
        try:
            await self._backend.append(path, content)
        except Exception:
            # If the note doesn't exist yet, create it
            await self._backend.put(path, content)

    async def append_to_inbox(self, message: str, source: str = "chat") -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        path = f"00-Inbox/Daily/{today}.md"
        ts = datetime.now().strftime("%H:%M")
        entry = f"\n- **{ts}** ({source}): {message}\n"
        try:
            await self.append_to_note(path, entry)
        except Exception:
            await self.create_note(path, f"# {today}\n{entry}")
        return path
