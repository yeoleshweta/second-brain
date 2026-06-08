"""Project Gutenberg via Gutendex (public domain books)."""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from loguru import logger

GUTENDEX_BASE = "https://gutendex.com"


@dataclass
class BookResult:
    id: int
    title: str
    authors: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    formats: dict[str, str] = field(default_factory=dict)
    source: str = "gutenberg"
    download_count: int = 0

    @property
    def canonical_url(self) -> str:
        return f"https://www.gutenberg.org/ebooks/{self.id}"

    @property
    def author_line(self) -> str:
        return ", ".join(self.authors) if self.authors else "Unknown author"

    @property
    def subject_tags(self) -> list[str]:
        tags: list[str] = []
        for subject in self.subjects[:6]:
            cleaned = subject.split("--")[0].strip().lower()
            if cleaned and cleaned not in tags:
                tags.append(cleaned.replace(" ", "-")[:40])
        return tags[:4]


def _parse_book(raw: dict) -> BookResult:
    authors = [a.get("name", "") for a in raw.get("authors", []) if a.get("name")]
    return BookResult(
        id=int(raw["id"]),
        title=str(raw.get("title") or "Untitled").strip(),
        authors=authors,
        subjects=[str(s) for s in raw.get("subjects", [])],
        languages=[str(code) for code in raw.get("languages", [])],
        formats={k: v for k, v in (raw.get("formats") or {}).items() if v},
        download_count=int(raw.get("download_count") or 0),
    )


async def search_gutenberg(query: str, *, limit: int = 5) -> list[BookResult]:
    params: dict[str, str | int] = {"search": query.strip()}
    if limit:
        params["page_size"] = limit
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{GUTENDEX_BASE}/books", params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Gutendex search failed for '{}': {}", query, exc)
            return []
    return [_parse_book(item) for item in data.get("results", [])[:limit]]


async def get_gutenberg_book(book_id: int) -> BookResult | None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{GUTENDEX_BASE}/books/{book_id}")
            resp.raise_for_status()
            return _parse_book(resp.json())
        except Exception as exc:
            logger.warning("Gutendex fetch failed for book {}: {}", book_id, exc)
            return None


def pick_read_format(formats: dict[str, str]) -> tuple[str, str] | None:
    """Return (mime_key, url) for the best in-app readable format."""
    priority = (
        "text/plain; charset=utf-8",
        "text/plain; charset=us-ascii",
        "text/plain",
        "application/pdf",
        "application/epub+zip",
        "application/x-mobipocket-ebook",
    )
    for key in priority:
        if key in formats:
            return key, formats[key]
    for key, url in formats.items():
        if "text/plain" in key:
            return key, url
        if "pdf" in key:
            return key, url
    return None


def pick_best_match(books: list[BookResult], query: str) -> BookResult | None:
    if not books:
        return None
    q = query.lower().strip()
    for book in books:
        if q in book.title.lower():
            return book
    for book in books:
        if any(q in author.lower() for author in book.authors):
            return book
    return books[0]


BOOK_QUERY_ALIASES: dict[str, str] = {
    "bible": "king james bible",
    "holy bible": "king james bible",
    "the bible": "king james bible",
    "scripture": "bible",
    "quran": "koran",
    "koran": "quran",
}


def expand_book_queries(query: str) -> list[str]:
    """Return search variants, most specific first."""
    q = query.strip()
    if not q:
        return []
    lowered = q.lower()
    out: list[str] = [q]
    alias = BOOK_QUERY_ALIASES.get(lowered)
    if alias and alias not in out:
        out.append(alias)
    if lowered != q:
        out.append(lowered)
    return list(dict.fromkeys(out))


async def search_gutenberg_broad(query: str, *, limit: int = 8) -> list[BookResult]:
    """Search with alias expansion; dedupe by book id."""
    seen: set[int] = set()
    results: list[BookResult] = []
    for variant in expand_book_queries(query):
        for book in await search_gutenberg(variant, limit=limit):
            if book.id in seen:
                continue
            seen.add(book.id)
            results.append(book)
            if len(results) >= limit:
                return results
    return results


def book_has_download(book: BookResult) -> bool:
    return pick_read_format(book.formats) is not None
