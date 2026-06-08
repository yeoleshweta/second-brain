"""Open Library — book discovery and borrow links (no auto-download)."""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from loguru import logger

OL_SEARCH = "https://openlibrary.org/search.json"


@dataclass
class OpenLibraryBook:
    key: str
    title: str
    authors: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)
    cover_id: int | None = None
    first_publish_year: int | None = None
    edition_count: int = 0
    has_fulltext: bool = False
    public_scan: bool = False

    @property
    def url(self) -> str:
        work_key = self.key if self.key.startswith("/works/") else f"/works/{self.key}"
        return f"https://openlibrary.org{work_key}"

    @property
    def author_line(self) -> str:
        return ", ".join(self.authors) if self.authors else "Unknown author"


def _parse_hit(hit: dict) -> OpenLibraryBook:
    authors = [str(a) for a in (hit.get("author_name") or [])[:3]]
    return OpenLibraryBook(
        key=str(hit.get("key", "")),
        title=str(hit.get("title") or "Untitled").strip(),
        authors=authors,
        subjects=[str(s) for s in (hit.get("subject") or [])[:5]],
        cover_id=hit.get("cover_i"),
        first_publish_year=hit.get("first_publish_year"),
        edition_count=int(hit.get("edition_count") or 0),
        has_fulltext=bool(hit.get("has_fulltext")),
        public_scan=bool(hit.get("public_scan_b")),
    )


async def search_open_library(query: str, *, limit: int = 5) -> list[OpenLibraryBook]:
    params = {
        "q": query.strip(),
        "limit": limit,
        "fields": (
            "key,title,author_name,subject,cover_i,first_publish_year,"
            "edition_count,has_fulltext,public_scan_b"
        ),
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(OL_SEARCH, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Open Library search failed for '{}': {}", query, exc)
            return []
    return [_parse_hit(doc) for doc in data.get("docs", [])[:limit]]
