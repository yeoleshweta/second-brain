"""LibriVox — free public-domain audiobooks."""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from loguru import logger

LIBRIVOX_API = "https://librivox.org/api/feed/audiobooks"


@dataclass
class AudiobookResult:
    id: int
    title: str
    authors: list[str] = field(default_factory=list)
    language: str = "English"
    url: str = ""
    duration_secs: int = 0
    sections: int = 0

    @property
    def author_line(self) -> str:
        return ", ".join(self.authors) if self.authors else "Unknown narrator/author"

    @property
    def duration_label(self) -> str:
        if not self.duration_secs:
            return ""
        hours = self.duration_secs // 3600
        mins = (self.duration_secs % 3600) // 60
        if hours:
            return f"{hours}h {mins}m"
        return f"{mins}m"


def _parse_audiobook(raw: dict) -> AudiobookResult:
    authors: list[str] = []
    for author in raw.get("authors", []) or []:
        if isinstance(author, dict) and author.get("first_name"):
            name = f"{author.get('first_name', '')} {author.get('last_name', '')}".strip()
            if name:
                authors.append(name)
    url = str(raw.get("url_librivox") or raw.get("url_project") or "")
    if url and not url.startswith("http"):
        url = f"https://librivox.org{url}"
    return AudiobookResult(
        id=int(raw.get("id") or 0),
        title=str(raw.get("title") or "Untitled").strip(),
        authors=authors,
        language=str(raw.get("language") or "English"),
        url=url,
        duration_secs=int(raw.get("totaltimesecs") or 0),
        sections=int(raw.get("num_sections") or 0),
    )


async def search_librivox(query: str, *, limit: int = 5) -> list[AudiobookResult]:
    params = {"format": "json", "search": query.strip(), "limit": limit}
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(LIBRIVOX_API, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("LibriVox search failed for '{}': {}", query, exc)
            return []
    books = data.get("books") or data
    if isinstance(books, dict):
        books = [books]
    return [_parse_audiobook(item) for item in books[:limit] if isinstance(item, dict)]
