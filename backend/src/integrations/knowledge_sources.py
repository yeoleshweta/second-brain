"""Knowledge sources: RSS feeds, arXiv search, optional Tavily web search, OpenAI web search."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

import arxiv
import feedparser
import httpx
from loguru import logger
from openai import AsyncOpenAI

from src.config import get_settings


@dataclass
class KnowledgeItem:
    title: str
    url: str
    summary: str
    source: str
    published: datetime | None = None

    def to_markdown(self) -> str:
        date = self.published.strftime("%Y-%m-%d") if self.published else "—"
        return (
            f"### [{self.title}]({self.url})\n"
            f"*{self.source} · {date}*\n\n"
            f"{self.summary}\n"
        )


async def fetch_rss(feed_urls: list[str], max_per_feed: int = 5) -> list[KnowledgeItem]:
    """Fetch and parse a list of RSS/Atom feeds in parallel."""
    async def _one(url: str) -> list[KnowledgeItem]:
        try:
            feed = await asyncio.to_thread(feedparser.parse, url)
            items = []
            for entry in feed.entries[:max_per_feed]:
                pub = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub = datetime(*entry.published_parsed[:6])
                items.append(
                    KnowledgeItem(
                        title=entry.get("title", "(untitled)"),
                        url=entry.get("link", ""),
                        summary=entry.get("summary", "")[:500],
                        source=feed.feed.get("title", url),
                        published=pub,
                    )
                )
            return items
        except Exception as e:
            logger.warning("RSS fetch failed for {}: {}", url, e)
            return []

    results = await asyncio.gather(*[_one(u) for u in feed_urls])
    return [item for sublist in results for item in sublist]


async def search_arxiv(query: str, max_results: int = 10) -> list[KnowledgeItem]:
    """Search arXiv for papers matching the query, sorted by submission date."""
    def _search():
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        return list(arxiv.Client().results(search))

    try:
        papers = await asyncio.to_thread(_search)
    except Exception as e:
        logger.warning("arXiv search failed: {}", e)
        return []

    return [
        KnowledgeItem(
            title=p.title,
            url=p.entry_id,
            summary=p.summary[:500],
            source="arXiv",
            published=p.published,
        )
        for p in papers
    ]


async def search_openai_web(query: str, max_results: int = 5) -> list[KnowledgeItem]:
    """Web search via OpenAI's gpt-4o-mini-search-preview (no separate API key needed)."""
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini-search-preview",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Find the {max_results} most recent and significant news stories or developments "
                        f"about: {query}. For each, include a brief 1-2 sentence summary and its URL."
                    ),
                }
            ],
        )
    except Exception as e:
        logger.warning("OpenAI web search failed: {}", e)
        return []

    message = resp.choices[0].message
    annotations = getattr(message, "annotations", None) or []

    items: list[KnowledgeItem] = []
    seen: set[str] = set()
    for ann in annotations:
        try:
            uc = ann.url_citation  # type: ignore[attr-defined]
            url: str = uc.url
            title: str = uc.title or url
        except AttributeError:
            continue
        if not url or url in seen:
            continue
        seen.add(url)
        items.append(
            KnowledgeItem(title=title, url=url, summary="", source="Web", published=None)
        )
        if len(items) >= max_results:
            break

    return items


async def search_tavily(query: str, max_results: int = 5) -> list[KnowledgeItem]:
    """Optional: web search via Tavily (requires TAVILY_API_KEY)."""
    settings = get_settings()
    if not settings.tavily_api_key:
        return []
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.tavily_api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("Tavily search failed: {}", e)
            return []

    return [
        KnowledgeItem(
            title=r["title"],
            url=r["url"],
            summary=r.get("content", "")[:500],
            source="Tavily",
        )
        for r in data.get("results", [])
    ]
