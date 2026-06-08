"""Knowledge sources: RSS, arXiv, Tavily/OpenAI web search, GitHub context."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import arxiv
import feedparser
import httpx
import yaml
from loguru import logger
from openai import AsyncOpenAI

from src.config import get_settings

# ── Feed configuration ────────────────────────────────────────────────────────


@dataclass
class FeedSource:
    url: str
    name: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def primary_tag(self) -> str:
        return self.tags[0] if self.tags else "general"


# Legacy inline defaults — used only when feeds.yaml is missing.
DEFAULT_FEEDS: dict[str, list[str]] = {
    "ai": [
        "https://openai.com/blog/rss.xml",
        "https://www.anthropic.com/news/rss.xml",
        "https://huggingface.co/blog/feed.xml",
    ],
    "engineering": [
        "https://martinfowler.com/feed.atom",
        "https://hnrss.org/frontpage",
    ],
    "science": [
        "https://www.quantamagazine.org/feed/",
        "https://phys.org/rss-feed/",
    ],
    "business": [
        "https://stratechery.com/feed/",
        "https://a16z.com/feed/",
    ],
    "design": [
        "https://www.smashingmagazine.com/feed/",
        "https://www.nngroup.com/feed/rss/",
    ],
    "psychology": [
        "https://www.astralcodexten.com/feed",
        "https://aeon.co/feed.rss",
    ],
}

# Map digest phrasing → feed tags for topic-filtered pulls.
TOPIC_TAG_ALIASES: dict[str, tuple[str, ...]] = {
    "ai": ("ai", "llm", "machine learning", "artificial intelligence", "agents"),
    "engineering": ("engineering", "software", "developer", "tech", "programming"),
    "science": ("science", "research", "physics", "biology", "neuroscience"),
    "business": ("business", "startup", "strategy", "economics", "market"),
    "design": ("design", "ux", "ui", "product design"),
    "psychology": ("psychology", "mental", "cognitive", "behavior"),
    "culture": ("culture", "ideas", "philosophy"),
    "health": ("health", "medicine", "fitness"),
    "finance": ("finance", "investing", "fintech"),
}


def _normalize_tag(tag: str) -> str:
    return tag.strip().lower()


def _feeds_config_path() -> Path:
    settings = get_settings()
    path = settings.knowledge_feeds_config
    if path.is_absolute():
        return path
    # Resolve relative to backend package root (parent of src/).
    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / path


@lru_cache(maxsize=1)
def load_feed_sources() -> list[FeedSource]:
    """Load tagged feeds from YAML. Returns empty list if file missing."""
    path = _feeds_config_path()
    if not path.exists():
        logger.debug("Feeds config not found at {}", path)
        return []

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning("Failed to parse feeds config {}: {}", path, exc)
        return []

    out: list[FeedSource] = []
    for entry in raw.get("feeds", []):
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("url", "")).strip()
        if not url:
            continue
        tags = [_normalize_tag(t) for t in entry.get("tags", []) if str(t).strip()]
        out.append(
            FeedSource(
                url=url,
                name=str(entry.get("name", "")).strip(),
                tags=tags or ["general"],
            )
        )
    logger.info("Loaded {} tagged feeds from {}", len(out), path)
    return out


def _legacy_feed_sources(interests: list[str]) -> list[FeedSource]:
    urls = get_feeds_for_interests_legacy(interests)
    return [FeedSource(url=u, name=u, tags=["general"]) for u in urls]


def get_feeds_for_interests_legacy(interests: list[str]) -> list[str]:
    """Return RSS URLs from inline DEFAULT_FEEDS dict (legacy fallback)."""
    urls: list[str] = []
    seen: set[str] = set()
    for genre in interests:
        for url in DEFAULT_FEEDS.get(_normalize_tag(genre), []):
            if url not in seen:
                seen.add(url)
                urls.append(url)
    if not urls:
        for url in DEFAULT_FEEDS["ai"]:
            urls.append(url)
    return urls


def resolve_feed_sources(
    interests: list[str],
    *,
    topic_tags: list[str] | None = None,
) -> list[FeedSource]:
    """Resolve feed list: env override > YAML > legacy defaults.

    When ``topic_tags`` is set, only feeds whose tags overlap are returned.
    """
    settings = get_settings()

    if settings.rss_feed_list:
        sources = [
            FeedSource(url=u, name=u, tags=["custom"])
            for u in settings.rss_feed_list
        ]
    else:
        sources = load_feed_sources()
        if not sources:
            sources = _legacy_feed_sources(interests)

    if not topic_tags:
        # Match user's declared interests.
        wanted = {_normalize_tag(i) for i in interests}
        if wanted:
            filtered = [
                s for s in sources if wanted.intersection(set(s.tags))
            ]
            if filtered:
                sources = filtered
        return sources

    wanted_topics = {_normalize_tag(t) for t in topic_tags}
    filtered = [s for s in sources if wanted_topics.intersection(set(s.tags))]
    return filtered or sources


def extract_topic_tags_from_message(message: str) -> list[str] | None:
    """If the user asked about a specific topic, return matching feed tags."""
    lowered = message.lower()
    matched: list[str] = []
    for tag, aliases in TOPIC_TAG_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            matched.append(tag)
    return matched or None


def get_feeds_for_interests(interests: list[str]) -> list[str]:
    """Backward-compatible URL list for callers that only need URLs."""
    return [s.url for s in resolve_feed_sources(interests)]


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
    """Fetch RSS by URL list (legacy API)."""
    sources = [FeedSource(url=u, name=u) for u in feed_urls]
    return await fetch_rss_sources(sources, max_per_feed=max_per_feed)


async def fetch_rss_sources(
    sources: list[FeedSource],
    max_per_feed: int = 5,
) -> list[KnowledgeItem]:
    """Fetch and parse tagged RSS/Atom feeds in parallel."""
    async def _one(source: FeedSource) -> list[KnowledgeItem]:
        try:
            feed = await asyncio.wait_for(
                asyncio.to_thread(feedparser.parse, source.url),
                timeout=8.0,
            )
            items = []
            display_source = source.name or feed.feed.get("title", source.url)
            for entry in feed.entries[:max_per_feed]:
                pub = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub = datetime(*entry.published_parsed[:6])
                items.append(
                    KnowledgeItem(
                        title=entry.get("title", "(untitled)"),
                        url=entry.get("link", ""),
                        summary=entry.get("summary", "")[:500],
                        source=display_source,
                        published=pub,
                        genre=source.primary_tag,
                    )
                )
            return items
        except TimeoutError:
            logger.warning("RSS fetch timed out for {}", source.url)
            return []
        except Exception as e:
            logger.warning("RSS fetch failed for {}: {}", source.url, e)
            return []

    if not sources:
        return []
    results = await asyncio.gather(*[_one(s) for s in sources])
    return [item for sublist in results for item in sublist]


def balance_items_by_tag(
    items: list[KnowledgeItem],
    *,
    max_per_tag: int = 4,
    max_total: int = 30,
) -> list[KnowledgeItem]:
    """Interleave items so one tag doesn't dominate the candidate pool."""
    by_tag: dict[str, list[KnowledgeItem]] = {}
    for item in items:
        tag = item.genre or "general"
        by_tag.setdefault(tag, []).append(item)

    out: list[KnowledgeItem] = []
    seen_urls: set[str] = set()
    tags = list(by_tag.keys())
    idx = 0
    while len(out) < max_total:
        progressed = False
        for tag in tags:
            bucket = by_tag[tag]
            if not bucket:
                continue
            taken = sum(1 for i in out if (i.genre or "general") == tag)
            if taken >= max_per_tag:
                continue
            item = bucket.pop(0)
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            out.append(item)
            progressed = True
            if len(out) >= max_total:
                break
        if not progressed:
            break
        idx += 1
    return out


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
                        f"Find the {max_results} most recent news stories or developments "
                        f"from the past 7 days about: {query}. Prefer items published this "
                        "week. For each, include a brief 1-2 sentence summary and its URL."
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


def _parse_published_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    for candidate in (text, text[:10]):
        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            continue
    return None


async def search_tavily(query: str, max_results: int = 5) -> list[KnowledgeItem]:
    """Optional: web search via Tavily (requires TAVILY_API_KEY)."""
    return await search_tavily_with_options(
        query,
        max_results=max_results,
        topic="news",
        days=7,
    )


async def search_tavily_with_options(
    query: str,
    *,
    max_results: int = 8,
    topic: str = "general",
    days: int | None = None,
) -> list[KnowledgeItem]:
    """Tavily search with configurable topic (general for research, news for digests)."""
    settings = get_settings()
    if not settings.tavily_api_key:
        return []
    payload: dict = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "topic": topic,
    }
    if days is not None and topic == "news":
        payload["days"] = days
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post("https://api.tavily.com/search", json=payload)
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
            published=_parse_published_date(r.get("published_date")),
        )
        for r in data.get("results", [])
    ]
