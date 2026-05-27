"""Obsidian Local REST API client.

Requires the 'Local REST API' Obsidian plugin (Settings -> Community plugins).
Plugin uses HTTPS with a self-signed cert on 127.0.0.1, hence verify=False.
"""
from __future__ import annotations

from datetime import datetime

import httpx
from loguru import logger

from src.config import get_settings


class ObsidianClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.obsidian_api_key:
            raise RuntimeError("OBSIDIAN_API_KEY not set in .env")
        self._client = httpx.AsyncClient(
            base_url=settings.obsidian_base_url,
            headers={"Authorization": f"Bearer {settings.obsidian_api_key}"},
            timeout=15.0,
            verify=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> ObsidianClient:
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    async def get_note(self, path: str) -> str:
        resp = await self._client.get(f"/vault/{path}")
        resp.raise_for_status()
        return resp.text

    async def create_note(self, path: str, content: str) -> None:
        logger.info("Obsidian PUT {}", path)
        resp = await self._client.put(
            f"/vault/{path}",
            content=content.encode("utf-8"),
            headers={"Content-Type": "text/markdown"},
        )
        resp.raise_for_status()

    async def append_to_note(self, path: str, content: str) -> None:
        logger.info("Obsidian POST {}", path)
        resp = await self._client.post(
            f"/vault/{path}",
            content=content.encode("utf-8"),
            headers={"Content-Type": "text/markdown"},
        )
        resp.raise_for_status()

    async def append_to_inbox(self, message: str, source: str = "chat") -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        path = f"00-Inbox/Daily/{today}.md"
        ts = datetime.now().strftime("%H:%M")
        entry = f"\n- **{ts}** ({source}): {message}\n"
        try:
            await self.append_to_note(path, entry)
        except httpx.HTTPStatusError:
            await self.create_note(path, f"# {today}\n{entry}")
        return path
