"""Knowledge sources: RSS, arXiv, Tavily/OpenAI web search, GitHub context."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

import arxiv
import feedparser
import httpx
from loguru import logger
from openai import AsyncOpenAI

from src.config import get_settings

# ── Multi-genre default RSS feeds ─────────────────────────────────────────────
# Organised by genre tag so we can filter by user interests.

DEFAULT_FEEDS: dict[str, list[str]] = {
    "ai": [
        "https://openai.com/blog/rss.xml",
        "https://www.anthropic.com/news/rss.xml",
        "https://bair.berkeley.edu/blog/feed.xml",
        "https://huggingface.co/blog/feed.xml",
    ],
    "engineering": [
        "https://engineering.atspotify.com/feed/",
        "https://netflixtechblog.com/feed",
        "https://martinfowler.com/feed.atom",
        "https://feeds.feedburner.com/TheDailyWtf",
    ],
    "science": [
        "https://www.nature.com/news.rss",
        "https://www.sciencedaily.com/rss/top.xml",
        "https://www.newscientist.com/feed/home/",
        "https://phys.org/rss-feed/",
    ],
    "business": [
        "https://hbr.org/jobs/rss",
        "https://feeds.feedburner.com/fastcompany/headlines",
        "https://www.inc.com/rss",
        "https://a16z.com/feed/",
    ],
    "design": [
        "https://www.smashingmagazine.com/feed/",
        "https://uxdesign.cc/feed",
        "https://feeds.feedburner.com/awwwards-website-awards",
        "https://medium.com/feed/microsoft-design",
    ],
    "psychology": [
        "https://fs.blog/feed/",         # Farnam Street — mental models
        "https://www.psychologytoday.com/us/front/feed",
        "https://behavioralscientist.org/feed/",
    ],
    "culture": [
        "https://aeon.co/feed.rss",
        "https://nautil.us/feed/",
        "https://www.theatlantic.com/feed/all/",
    ],
    "health": [
        "https://well.blogs.nytimes.com/feed/",
        "https://www.health.harvard.edu/blog/feed",
    ],
    "finance": [
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://www.bloomberg.com/feeds/sitemap_news.xml",
    ],
}


def get_feeds_for_interests(interests: list[str]) -> list[str]:
    """Return RSS URLs matching the user's interest list, deduplicated."""
    urls: list[str] = []
    seen: set[str] = set()
    for genre in interests:
        for url in DEFAULT_FEEDS.get(genre.lower(), []):
            if url not in seen:
                seen.add(url)
                urls.append(url)
    # Fallback: if no interests match, return all AI feeds
    if not urls:
        for url in DEFAULT_FEEDS["ai"]:
            urls.append(url)
    return urls


# ── KnowledgeItem ─────────────────────────────────────────────────────────────


@dataclass
class KnowledgeItem:
    title: str
    url: str
    summary: str
    source: str
    published: datetime | None = None
    genre: str = ""  # populated when known

    def to_markdown(self) -> str:
        date = self.published.strftime("%Y-%m-%d") if self.published else "—"
        return (
            f"### [{self.title}]({self.url})\n"
            f"*{self.source} · {date}*\n\n"
            f"{self.summary}\n"
        )


# ── GitHub context ────────────────────────────────────────────────────────────


@dataclass
class GitHubProfile:
    username: str
    languages: list[str] = field(default_factory=list)   # top languages by repo count
    topics: list[str] = field(default_factory=list)       # aggregated repo topics
    repo_names: list[str] = field(default_factory=list)   # recent repo names
    bio: str = ""

    def to_context_string(self) -> str:
        parts = []
        if self.bio:
            parts.append(f"Bio: {self.bio}")
        if self.languages:
            parts.append(f"Top languages: {', '.join(self.languages[:5])}")
        if self.topics:
            parts.append(f"Project topics: {', '.join(self.topics[:10])}")
        if self.repo_names:
            parts.append(f"Recent projects: {', '.join(self.repo_names[:8])}")
        return " | ".join(parts) if parts else ""


async def fetch_github_profile(username: str, token: str | None = None) -> GitHubProfile:
    """Fetch public repo metadata to build a user interest profile."""
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        try:
            # User bio
            user_resp = await client.get(f"https://api.github.com/users/{username}")
            user_resp.raise_for_status()
            user_data = user_resp.json()
            bio = (user_data.get("bio") or "").strip()

            # Repos (sorted by updated)
            repos_resp = await client.get(
                f"https://api.github.com/users/{username}/repos",
                params={"sort": "updated", "per_page": 30},
            )
            repos_resp.raise_for_status()
            repos = repos_resp.json()
        except Exception as e:
            logger.warning("GitHub profile fetch failed for {}: {}", username, e)
            return GitHubProfile(username=username)

    lang_counts: dict[str, int] = {}
    all_topics: list[str] = []
    names: list[str] = []

    for repo in repos:
        if repo.get("fork"):
            continue  # skip forks — they dilute signal
        name = repo.get("name", "")
        if name:
            names.append(name)
        lang = repo.get("language")
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        for topic in repo.get("topics", []):
            all_topics.append(topic)

    top_langs = sorted(lang_counts, key=lang_counts.__getitem__, reverse=True)
    # Dedupe topics preserving order
    seen_t: set[str] = set()
    unique_topics = [t for t in all_topics if not (t in seen_t or seen_t.add(t))]  # type: ignore[func-returns-value]

    profile = GitHubProfile(
        username=username,
        languages=top_langs,
        topics=unique_topics[:15],
        repo_names=names[:10],
        bio=bio,
    )
    logger.info(
        "GitHub profile for {}: {} repos, langs={}, topics={}",
        username, len(names), top_langs[:3], unique_topics[:5],
    )
    return profile


# ── RSS ───────────────────────────────────────────────────────────────────────


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


# ── arXiv ────────────────────────────────────────────────────────────────────


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
            genre="science",
        )
        for p in papers
    ]


# ── OpenAI web search ─────────────────────────────────────────────────────────


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
                        f"Find the {max_results} most recent and significant news stories "
                        f"or developments about: {query}. For each, include a brief "
                        "1-2 sentence summary and its URL."
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


# ── Tavily ───────────────────────────────────────────────────────────────────


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
