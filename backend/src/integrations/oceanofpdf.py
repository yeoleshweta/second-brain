"""Ocean of PDF links — search URL always; optional direct page via web search."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus, urlparse

import httpx
from loguru import logger

from src.config import get_settings
from src.integrations.knowledge_sources import KnowledgeItem, search_openai_web

OCEANOFPDF_BASE = "https://oceanofpdf.com/"
OCEANOFPDF_HOST = "oceanofpdf.com"
BOOK_PATH = "/books/"
MIN_DIRECT_MATCH_SCORE = 0.45


@dataclass
class OceanOfPdfMatch:
    title: str
    url: str
    score: float
    is_search: bool = False


def oceanofpdf_search_url(query: str) -> str:
    """Site search link, e.g. https://oceanofpdf.com/?s=atomic+habits"""
    return f"{OCEANOFPDF_BASE}?s={quote_plus(query.strip())}"


def oceanofpdf_search_match(query: str) -> OceanOfPdfMatch:
    q = query.strip()
    return OceanOfPdfMatch(
        title=q,
        url=oceanofpdf_search_url(q),
        score=1.0,
        is_search=True,
    )


def _normalize(text: str) -> set[str]:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return {w for w in cleaned.split() if len(w) > 1}


def _title_match_score(query: str, candidate: str) -> float:
    q = _normalize(query)
    if not q:
        return 0.0
    c = _normalize(candidate)
    return len(q & c) / len(q)


def _title_from_oceanofpdf_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path.startswith("books/"):
        return ""
    slug = path.removeprefix("books/").strip("/")
    if "-pdf-" in slug:
        slug = slug.split("-pdf-", 1)[0]
    return slug.replace("-", " ").strip()


def _normalize_book_page_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if OCEANOFPDF_HOST not in parsed.netloc.lower():
        return ""
    if BOOK_PATH not in parsed.path.lower():
        return ""
    path = parsed.path.rstrip("/") + "/"
    return f"https://{OCEANOFPDF_HOST}{path}"


def _score_candidate(query: str, url: str, result_title: str) -> float:
    from_slug = _title_from_oceanofpdf_url(url)
    slug_score = _title_match_score(query, from_slug) if from_slug else 0.0
    title_score = _title_match_score(query, result_title)
    return max(slug_score, title_score)


async def _search_web(query: str, *, max_results: int = 6) -> list[KnowledgeItem]:
    settings = get_settings()
    if settings.tavily_api_key:
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
                        "include_domains": [OCEANOFPDF_HOST],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.warning("Tavily Ocean of PDF lookup failed: {}", exc)
                return []
        return [
            KnowledgeItem(
                title=r.get("title", ""),
                url=r.get("url", ""),
                summary=r.get("content", "")[:300],
                source="Tavily",
            )
            for r in data.get("results", [])
        ]
    return await search_openai_web(query, max_results=max_results)


async def lookup_oceanofpdf_book_page(query: str) -> OceanOfPdfMatch | None:
    """Optional: direct /books/ page if web search finds a close match."""
    q = query.strip()
    if len(q) < 2:
        return None

    searches = [
        f'site:{OCEANOFPDF_HOST} "{q}" pdf',
        f"{OCEANOFPDF_HOST} {q} pdf book",
    ]
    seen_urls: set[str] = set()
    best: OceanOfPdfMatch | None = None

    for search_query in searches:
        results = await _search_web(search_query, max_results=6)
        for item in results:
            url = _normalize_book_page_url(item.url or "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            title = item.title.strip() or _title_from_oceanofpdf_url(url) or q
            score = _score_candidate(q, url, title)
            if score < MIN_DIRECT_MATCH_SCORE:
                continue
            candidate = OceanOfPdfMatch(title=title, url=url, score=score, is_search=False)
            if best is None or candidate.score > best.score:
                best = candidate
        if best and best.score >= 0.75:
            break

    if best:
        logger.info(
            "Ocean of PDF book page for '{}': {} (score={:.2f})",
            q,
            best.url,
            best.score,
        )
    return best


async def resolve_oceanofpdf(query: str) -> OceanOfPdfMatch:
    """Always return site search URL; use direct book page when web search finds one."""
    q = query.strip()
    direct = await lookup_oceanofpdf_book_page(q)
    if direct:
        return direct
    return oceanofpdf_search_match(q)
