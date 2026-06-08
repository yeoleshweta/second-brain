"""Find unofficial book PDF links via web search (Tavily), before Ocean of PDF fallback."""
from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from loguru import logger

from src.config import get_settings
from src.integrations.knowledge_sources import KnowledgeItem, search_openai_web

PDF_HINT_RE = re.compile(r"\.pdf($|\?)|/pdf/|filetype:pdf|download.*pdf", re.IGNORECASE)
SKIP_HOSTS = frozenset({"oceanofpdf.com", "www.oceanofpdf.com"})


def _looks_like_pdf_link(url: str, title: str, snippet: str) -> bool:
    combined = f"{url} {title} {snippet}".lower()
    if PDF_HINT_RE.search(combined):
        return True
    path = urlparse(url).path.lower()
    return path.endswith(".pdf")


async def _tavily_search(query: str, *, max_results: int = 6) -> list[KnowledgeItem]:
    settings = get_settings()
    if not settings.tavily_api_key:
        return await search_openai_web(query, max_results=max_results)

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.tavily_api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                    "topic": "general",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Tavily book PDF search failed: {}", exc)
            return []

    return [
        KnowledgeItem(
            title=r.get("title", ""),
            url=r.get("url", ""),
            summary=(r.get("content") or "")[:400],
            source="Tavily",
        )
        for r in data.get("results", [])
        if r.get("url")
    ]


async def search_web_book_pdf_links(query: str, *, max_results: int = 4) -> list[KnowledgeItem]:
    """Search the open web for direct or landing PDF links for a book title."""
    q = query.strip()
    if len(q) < 2:
        return []

    searches = [
        f'"{q}" pdf download ebook',
        f"{q} book pdf free download",
    ]
    seen: set[str] = set()
    hits: list[KnowledgeItem] = []

    for search_query in searches:
        results = await _tavily_search(search_query, max_results=8)
        for item in results:
            url = (item.url or "").strip()
            if not url or url in seen:
                continue
            host = urlparse(url).netloc.lower().removeprefix("www.")
            if host in SKIP_HOSTS:
                continue
            if not _looks_like_pdf_link(url, item.title, item.summary):
                continue
            seen.add(url)
            hits.append(item)
            if len(hits) >= max_results:
                return hits

    return hits
