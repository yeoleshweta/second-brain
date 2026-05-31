"""Ross — Knowledge Agent.

Handles saving URLs/notes to the reading list, reading list management,
on-demand digests, and building the morning brief. Does NOT fall back
to stub_run — chat-only replies stay in chat, nothing leaks to the inbox.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx
from loguru import logger
from openai import AsyncOpenAI
from sqlmodel import Session

from src.config import get_settings
from src.integrations import ObsidianClient
from src.integrations.knowledge_sources import (
    GitHubProfile,
    KnowledgeItem,
    fetch_github_profile,
    fetch_rss,
    get_feeds_for_interests,
    search_arxiv,
    search_openai_web,
    search_tavily,
)
from src.services import reading_list as rl
from src.storage import ReadingListItem, get_session, init_db
from src.storage.models import ItemKind, ItemStatus

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState

# ── Constants ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Ross, the knowledge curator in a personal AI second-brain app.
You help the user save articles, manage their reading list, and stay current on AI news.
Be friendly, concise, and mildly nerdy. Use second person ("your reading list").
When uncertain, ask rather than guess. Do not pretend to have feelings."""

ARXIV_QUERY = "language models OR LLM OR diffusion OR agent"
TO_READ_DIR = "01-Knowledge/To-Read"
ARCHIVE_DIR = "01-Knowledge/Archive"

# ── Intent patterns ────────────────────────────────────────────────────────────

SAVE_RE = re.compile(
    r"\b(save in notes|save this|save it|save to (notes|list|reading list)|"
    r"bookmark this|bookmark it|add to (reading list|notes|list)|"
    r"remember this|file this)\b",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://\S+")

LIST_RE = re.compile(
    r"\b(show (my )?reading list|what'?s in (my )?reading list|reading list)\b",
    re.IGNORECASE,
)
MARK_READ_RE = re.compile(
    r"\b(mark .+ as read|finished reading .+|i (just )?finished .+)\b",
    re.IGNORECASE,
)
PROGRESS_RE = re.compile(
    r"(\d+)%\s+(.+)|i'?m (\d+)%\s+done\s+with\s+(.+)",
    re.IGNORECASE,
)
DELETE_RE = re.compile(
    r"\b(delete|remove)\s+(.+?)\s+from\s+(my\s+)?list\b",
    re.IGNORECASE,
)
DIGEST_RE = re.compile(
    r"\b(what'?s new|any new|latest|new papers|ai news|new in ai|recent papers|whats new)\b",
    re.IGNORECASE,
)
SUMMARIZE_RE = re.compile(
    r"\b(summarize|summary|tldr|tl;dr|what does this say)\b",
    re.IGNORECASE,
)


def _extract_urls(msg: str) -> list[str]:
    return URL_RE.findall(msg)


def _domain(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else (netloc or "web")


def _slug(title: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower().strip()).strip("-")
    return slug[:max_len].rstrip("-")


def _short(text: str, n: int = 140) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= n else compact[: n - 1].rstrip() + "…"


def _format_date(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d") if dt else "n/a"


# ── URL fetching ───────────────────────────────────────────────────────────────


async def fetch_url_text(url: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(f"https://r.jina.ai/{url}", headers={"Accept": "text/plain"})
        r.raise_for_status()
        return r.text[:20_000]


async def _extract_article_fields(url: str, text: str) -> dict[str, Any]:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(
        model=settings.openai_model_main,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract metadata for a saved reading item. "
                    "Return JSON with keys: title (str), summary (2-3 sentences), "
                    "tags (array of ≤4 short lowercase strings)."
                ),
            },
            {"role": "user", "content": f"URL: {url}\n\n{text}"},
        ],
    )
    raw = (resp.choices[0].message.content or "{}").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


async def _make_title_for_note(body: str) -> str:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(
        model=settings.openai_model_cheap,
        max_tokens=20,
        messages=[
            {
                "role": "system",
                "content": "Generate a short title (≤60 chars) for this note. Return only the title, no quotes.",  # noqa: E501
            },
            {"role": "user", "content": body},
        ],
    )
    return (resp.choices[0].message.content or body[:60]).strip()


# ── Mirror file helpers ────────────────────────────────────────────────────────


def _mirror_frontmatter(item: ReadingListItem) -> str:
    tags_list = [t.strip() for t in item.tags.split(",") if t.strip()]
    tags_yaml = "[" + ", ".join(tags_list) + "]"
    return (
        "---\n"
        f"id: {item.id}\n"
        f"url: {item.url or ''}\n"
        f"source: {item.source or ''}\n"
        f"kind: {item.kind}\n"
        f"status: {item.status}\n"
        f"progress: {item.progress}\n"
        f"saved_at: {item.saved_at.strftime('%Y-%m-%dT%H:%M')}\n"
        f"tags: {tags_yaml}\n"
        "---\n\n"
        f"# {item.title}\n\n"
        f"*{item.source or 'note'} · saved {item.saved_at.strftime('%Y-%m-%d')}*\n\n"
        f"{item.summary or ''}\n"
    )


async def _write_mirror(item: ReadingListItem, obsidian: ObsidianClient) -> str:
    slug = _slug(item.title)
    path = f"{TO_READ_DIR}/{slug}.md"
    await obsidian.create_note(path, _mirror_frontmatter(item))
    return path


async def _rewrite_mirror_frontmatter(item: ReadingListItem, obsidian: ObsidianClient) -> None:
    if not item.mirror_path:
        return
    try:
        await obsidian.create_note(item.mirror_path, _mirror_frontmatter(item))
    except Exception as e:
        logger.warning("Could not rewrite mirror frontmatter for {}: {}", item.mirror_path, e)


async def _move_to_archive(item: ReadingListItem, obsidian: ObsidianClient) -> str | None:
    if not item.mirror_path:
        return None
    slug = _slug(item.title)
    archive_path = f"{ARCHIVE_DIR}/{slug}.md"
    try:
        content = await obsidian.get_note(item.mirror_path)
        # Update frontmatter status in content
        content = re.sub(r"^status: .+$", f"status: {ItemStatus.READ}", content, flags=re.MULTILINE)
        await obsidian.create_note(archive_path, content)
        # Delete from To-Read
        await _delete_mirror(item.mirror_path, obsidian)
    except Exception as e:
        logger.warning("Archive move failed for {}: {}", item.mirror_path, e)
        return None
    return archive_path


async def _delete_mirror(path: str, obsidian: ObsidianClient) -> None:
    try:
        # Obsidian Local REST API: DELETE /vault/<path>
        await obsidian._client.delete(f"/vault/{path}")
    except Exception as e:
        logger.warning("Mirror delete failed for {}: {}", path, e)


# ── Intent detection ───────────────────────────────────────────────────────────


def is_save_command(msg: str) -> bool:
    return bool(SAVE_RE.search(msg))


def is_list_command(msg: str) -> bool:
    return bool(LIST_RE.search(msg))


def is_mark_command(msg: str) -> tuple[bool, str]:
    m = MARK_READ_RE.search(msg)
    if not m:
        return False, ""
    # Extract the target title after "mark … as read" / "finished reading …"
    full = m.group(0)
    patterns = (
        r"mark\s+(.+?)\s+as\s+read",
        r"finished reading\s+(.+)",
        r"i just finished\s+(.+)",
        r"i finished\s+(.+)",
    )
    for pat in patterns:
        sub = re.search(pat, full, re.IGNORECASE)
        if sub:
            return True, sub.group(1).strip()
    return True, ""


def is_progress_command(msg: str) -> tuple[bool, int, str]:
    m = PROGRESS_RE.search(msg)
    if not m:
        return False, 0, ""
    if m.group(1):
        return True, int(m.group(1)), m.group(2).strip()
    return True, int(m.group(3)), m.group(4).strip()


def is_delete_command(msg: str) -> tuple[bool, str]:
    m = DELETE_RE.search(msg)
    if not m:
        return False, ""
    return True, m.group(2).strip()


def is_digest_command(msg: str) -> bool:
    return bool(DIGEST_RE.search(msg))


def is_summarize_command(msg: str) -> bool:
    return bool(_extract_urls(msg)) and bool(SUMMARIZE_RE.search(msg))


# ── Handlers ───────────────────────────────────────────────────────────────────


async def handle_save(msg: str, session: Session) -> dict:
    # Strip save phrase so it doesn't pollute the extracted content
    cleaned = SAVE_RE.sub("", msg).strip().lstrip(":").strip()
    urls = _extract_urls(cleaned) or _extract_urls(msg)

    title = cleaned
    summary: str | None = None
    source: str | None = None
    tags: str = ""
    kind = ItemKind.URL

    if urls:
        url = urls[0]
        source = _domain(url)
        kind = ItemKind.PAPER if "arxiv.org" in url else ItemKind.URL
        try:
            text = await fetch_url_text(url)
            parsed = await _extract_article_fields(url, text)
            title = str(parsed.get("title") or url).strip() or url
            summary = str(parsed.get("summary") or "").strip() or None
            raw_tags = parsed.get("tags") if isinstance(parsed.get("tags"), list) else []
            tags = ",".join(str(t) for t in raw_tags[:4])
        except Exception as e:
            logger.warning("URL extraction failed for {}: {}", url, e)
            title = url
    else:
        # Freeform note — no URL
        url = None
        kind = ItemKind.NOTE
        source = "note"
        try:
            title = await _make_title_for_note(cleaned)
        except Exception:
            title = cleaned[:60]

    item = rl.add(
        session,
        url=url if urls else None,
        title=title,
        summary=summary,
        source=source,
        kind=kind,
        tags=tags,
    )

    if item is None:
        # Dedup — find existing to show date
        from sqlmodel import select
        existing = session.exec(
            select(ReadingListItem).where(ReadingListItem.url == urls[0])
        ).first()
        date_str = existing.saved_at.strftime("%Y-%m-%d") if existing else "earlier"
        return {
            "reply": (
                f"You already have this in your list (saved {date_str}). "
                "Want to re-add it? Reply 'yes' to confirm."
            )
        }

    # Write mirror file
    mirror_path: str | None = None
    try:
        async with ObsidianClient() as obsidian:
            mirror_path = await _write_mirror(item, obsidian)
        item.mirror_path = mirror_path
        session.add(item)
        session.commit()
    except Exception as e:
        logger.warning("Mirror write failed: {}", e)

    return {
        "reply": f"🪄 Ross saved '{title}' to your reading list.",
        "obsidian_path": mirror_path,
    }


async def handle_list(session: Session) -> dict:
    items = rl.list_active(session)
    s = rl.stats(session)
    header = f"📚 {s['total']} total · {s['read']} read ({s['percent_done']}%)\n\n"

    if not items:
        return {
            "reply": (
                header
                + "Your reading list is empty. "
                "Save something with 'save in notes <url>'."
            )
        }

    lines = []
    for item in items:
        prog = f" · {item.progress}%" if item.progress else ""
        lines.append(f"- **{item.title}** ({item.source or 'note'} · {item.status}{prog})")

    return {"reply": header + "\n".join(lines)}


async def handle_mark_read(target: str, session: Session) -> dict:
    item = rl.find_by_title(session, target)
    if not item:
        return {
            "reply": (
                f"Couldn't find anything matching '{target}' in your list. "
                "Try 'show my reading list' to see what's there."
            )
        }

    rl.mark_read(session, item)

    # Move mirror file to archive
    try:
        async with ObsidianClient() as obsidian:
            new_path = await _move_to_archive(item, obsidian)
        if new_path:
            item.mirror_path = new_path
            session.add(item)
            session.commit()
    except Exception as e:
        logger.warning("Archive move failed: {}", e)

    s = rl.stats(session)
    return {
        "reply": (
            f"📚 Marked '{item.title}' as read. "
            f"{s['read']} of {s['total']} done ({s['percent_done']}%)."
        ),
        "obsidian_path": item.mirror_path,
    }


async def handle_progress(target: str, pct: int, session: Session) -> dict:
    item = rl.find_by_title(session, target)
    if not item:
        return {
            "reply": (
                f"Couldn't find anything matching '{target}' in your list."
            )
        }

    rl.update_progress(session, item, pct)

    try:
        async with ObsidianClient() as obsidian:
            await _rewrite_mirror_frontmatter(item, obsidian)
    except Exception as e:
        logger.warning("Progress mirror update failed: {}", e)

    return {"reply": f"Got it — '{item.title}' at {pct}%."}


async def handle_delete(target: str, session: Session) -> dict:
    item = rl.find_by_title(session, target)
    if not item:
        return {"reply": f"Couldn't find anything matching '{target}' in your list."}

    mirror = item.mirror_path
    rl.delete(session, item)

    if mirror:
        try:
            async with ObsidianClient() as obsidian:
                await _delete_mirror(mirror, obsidian)
        except Exception as e:
            logger.warning("Mirror delete failed: {}", e)

    return {"reply": f"🗑️ Deleted '{item.title}' from your list."}


async def _get_github_profile() -> GitHubProfile | None:
    settings = get_settings()
    if not settings.github_username:
        return None
    try:
        return await fetch_github_profile(settings.github_username, settings.github_token)
    except Exception as e:
        logger.warning("GitHub profile fetch skipped: {}", e)
        return None


def _build_arxiv_query(profile: GitHubProfile | None, interests: list[str]) -> str:
    """Build an arXiv query personalised to the user's GitHub work + interests."""
    base_terms = ["language model", "LLM", "agent", "diffusion"]
    if profile:
        # Add languages and topics as search hints
        for lang in profile.languages[:3]:
            if lang.lower() not in {"html", "css", "dockerfile", "shell"}:
                base_terms.append(lang.lower())
        for topic in profile.topics[:5]:
            base_terms.append(topic.replace("-", " "))
    # Add interest-derived terms
    interest_map = {
        "science": ["computational biology", "physics", "neuroscience"],
        "business": ["economics", "market", "operations research"],
        "design": ["human computer interaction", "visualization"],
        "psychology": ["cognitive science", "behavioral"],
        "health": ["medicine", "health informatics"],
    }
    for interest in interests:
        for term in interest_map.get(interest, []):
            base_terms.append(term)
    unique = list(dict.fromkeys(base_terms))[:8]
    return " OR ".join(unique)


def _build_web_query(profile: GitHubProfile | None, interests: list[str]) -> str:
    """Build a trending-search query covering the user's interests."""
    parts = []
    if profile and profile.topics:
        parts.append(" ".join(profile.topics[:3]))
    genre_queries = {
        "ai": "AI tools 2026 OR new LLM",
        "engineering": "software engineering 2026 OR developer tools",
        "science": "science breakthrough 2026",
        "business": "startup trends 2026 OR business strategy",
        "design": "design trends 2026 OR UX",
        "psychology": "psychology research 2026 OR mental models",
        "culture": "ideas culture 2026",
        "health": "health research 2026",
        "finance": "fintech 2026 OR investing",
    }
    for interest in interests[:3]:
        q = genre_queries.get(interest)
        if q:
            parts.append(q)
    return " OR ".join(parts) if parts else "AI tools 2026 OR new LLM benchmark"


async def handle_digest_now() -> dict:
    settings = get_settings()

    # Resolve feed list: user-defined or auto-selected from interests
    feed_urls = settings.rss_feed_list or get_feeds_for_interests(settings.interest_list)
    profile = await _get_github_profile()
    arxiv_query = _build_arxiv_query(profile, settings.interest_list)

    rss_items, arxiv_items = await asyncio.gather(
        fetch_rss(feed_urls, max_per_feed=3),
        search_arxiv(arxiv_query, max_results=8),
    )
    merged = _sort_recent(_dedupe([*rss_items, *arxiv_items]))[:10]
    if not merged:
        return {"reply": "🪄 Ross couldn't find fresh items right now. Try again in a bit."}

    structured = [
        {
            "title": item.title,
            "url": item.url,
            "summary": item.summary,
            "source": item.source or "",
            "date": _format_date(item.published),
            "kind": "paper" if "arxiv.org" in (item.url or "") else "url",
        }
        for item in merged
    ]

    context_note = ""
    if profile:
        context_note = f" (personalised for your {', '.join(profile.languages[:2])} projects)"

    reply = f"🪄 Ross found {len(merged)} fresh items{context_note}:"
    return {"reply": reply, "digest_items": structured}


async def handle_summarize_url(msg: str) -> dict:
    urls = _extract_urls(msg)
    if not urls:
        return {"reply": "I don't see a URL to summarize."}
    url = urls[0]
    source = _domain(url)
    try:
        text = await fetch_url_text(url)
        parsed = await _extract_article_fields(url, text)
        title = str(parsed.get("title") or url).strip()
        summary = str(parsed.get("summary") or "Could not summarize this URL.").strip()
    except Exception as e:
        logger.warning("Summarize URL failed for {}: {}", url, e)
        return {"reply": "I couldn't fetch that page right now. Please try again in a bit."}
    return {"reply": f"**{title}**\n\n{summary}\n\n*Source: {source}*"}


async def handle_chat(msg: str) -> dict:
    """Generic chat handler — no saves, no Obsidian writes."""
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    system = (
        "You are Ross, the knowledge curator in a personal AI second-brain app. "
        "The user is chatting about ideas, articles, research, or learning. "
        "Reply briefly (2-4 sentences). Do not pretend to save anything — if they want "
        "something saved, they need to say 'save in notes', 'save this', etc. "
        "Don't summarize from your training data — be candid when you'd need to look something up."
    )
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model_cheap,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": msg},
            ],
        )
        reply = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.warning("Ross chat LLM failed: {}", e)
        reply = "I'm having trouble right now — please try again."
    return {"reply": reply}


# ── Dedup / sort helpers ───────────────────────────────────────────────────────


def _dedupe(items: list[KnowledgeItem]) -> list[KnowledgeItem]:
    seen: set[str] = set()
    out: list[KnowledgeItem] = []
    for item in items:
        key = item.url.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _sort_recent(items: list[KnowledgeItem]) -> list[KnowledgeItem]:
    return sorted(items, key=lambda i: i.published or datetime.min, reverse=True)


# ── Morning Brief ──────────────────────────────────────────────────────────────


async def morning_section() -> str:
    """Curate a 3-item brief and return rendered Markdown (no file write).

    Exposed for the unified combined-brief job. Returns the `## 🪄 Ross's Picks`
    section as a string.
    """
    settings = get_settings()

    feed_urls = settings.rss_feed_list or get_feeds_for_interests(settings.interest_list)
    profile, rss_items, arxiv_items = await asyncio.gather(
        _get_github_profile(),
        fetch_rss(feed_urls, max_per_feed=5),
        search_arxiv(_build_arxiv_query(None, settings.interest_list), max_results=10),
    )
    web_query = _build_web_query(profile, settings.interest_list)
    web_items = await (
        search_tavily(web_query, max_results=5)
        if settings.tavily_api_key
        else search_openai_web(web_query, max_results=5)
    )

    candidates = _dedupe([*rss_items, *arxiv_items, *web_items])
    if not candidates:
        logger.warning("Morning brief: no candidates found")
        return "## 🪄 Ross's Picks\n\n_No items found today._\n"

    cand_lines = []
    for i, c in enumerate(candidates[:30], 1):
        cand_lines.append(
            f"{i}. [{c.source}] {c.title} ({_format_date(c.published)}) — "
            f"{_short(c.summary, 200)} — {c.url}"
        )
    cand_text = "\n".join(cand_lines)

    context_hint = ""
    if profile:
        context_hint = (
            f"\nUser context: {profile.to_context_string()}\n"
            "Prefer items relevant to the user's stack and interests, but still ensure diversity."
        )
    interests_str = ", ".join(settings.interest_list)

    prompt = (
        "You are Ross, curating a 3-item morning brief for the user.\n"
        f"User's interest areas: {interests_str}.{context_hint}\n\n"
        "From the candidates below, pick EXACTLY 3 items, one per category:\n"
        '- "trending": one trending or noteworthy item — could be AI, tech, science,'
        " business, design, or any other interest area\n"
        '- "interesting": one unique fact, surprising research finding, or'
        ' "did you know" item from ANY genre\n'
        '- "tool": one new or notable tool, library, product, or service the user'
        " might want to try\n\n"
        "For each pick, write a 2-3 sentence summary (NOT just the source blurb — write fresh"
        " prose). Vary genres across the 3 picks.\n"
        'Return JSON: {"trending": {"url": str, "title": str, "source": str, "date": str,'
        ' "blurb": str}, "interesting": {...}, "tool": {...}}\n\n'
        f"CANDIDATES:\n{cand_text}"
    )

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model_main,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        raw = (resp.choices[0].message.content or "{}").strip()
        picks = json.loads(raw)
    except Exception as e:
        logger.error("Morning brief LLM failed: {}", e)
        return "## 🪄 Ross's Picks\n\n_LLM error — try again later._\n"

    now = datetime.now()

    def _section(emoji: str, heading: str, key: str) -> str:
        item = picks.get(key, {})
        if not item:
            return f"## {emoji} {heading}\n\n_No item found._\n"
        title = item.get("title", "Untitled")
        url = item.get("url", "")
        source = item.get("source", "")
        date = item.get("date", "")
        blurb = item.get("blurb", "")
        link = f"[{title}]({url})" if url else title
        meta = " · ".join(filter(None, [source, date]))
        return (
            f"## {emoji} {heading}\n\n"
            f"**{link}** — *{meta}*\n\n"
            f"{blurb}\n"
        )

    return (
        f"## 🪄 Ross's Picks\n\n"
        f"*Curated by Ross at {now.strftime('%H:%M')}.*\n\n"
        + _section("🔥", "Trending", "trending") + "\n"
        + _section("🧠", "Interesting", "interesting") + "\n"
        + _section("🛠️", "New tool / tech", "tool") + "\n"
    )


async def build_morning_brief() -> str:
    """Write a Ross-only brief to Obsidian. Returns the vault path.

    Kept for backward compat with POST /api/jobs/morning-brief.
    For the unified daily brief, use combined_brief.build_combined_brief().
    """
    content_section = await morning_section()
    now = datetime.now()
    day = now.strftime("%Y-%m-%d")

    content = (
        f"# Ross's Morning Brief — {day}\n\n"
        f"*Generated at {now.strftime('%H:%M')}.*\n\n"
        + content_section
    )

    brief_path = f"00-Inbox/Daily/{day}-Ross.md"
    try:
        async with ObsidianClient() as obsidian:
            await obsidian.create_note(brief_path, content)
        logger.info("Morning brief written to {}", brief_path)
    except Exception as e:
        logger.error("Morning brief Obsidian write failed: {}", e)
        return ""

    return brief_path


# Backwards-compat alias
async def build_daily_brief() -> str:
    return await build_morning_brief()


# ── Main entry point ───────────────────────────────────────────────────────────


async def run(state: AgentState) -> dict:
    """Ross's main dispatch. Never writes to the inbox; never calls stub_run."""
    msg = state.get("user_message", "")

    # Ensure DB is ready (idempotent)
    init_db()

    with next(get_session()) as session:
        if is_save_command(msg):
            return await handle_save(msg, session)

        if is_list_command(msg):
            return await handle_list(session)

        ok, target = is_mark_command(msg)
        if ok:
            return await handle_mark_read(target, session)

        ok2, pct, target2 = is_progress_command(msg)
        if ok2:
            return await handle_progress(target2, pct, session)

        ok3, target3 = is_delete_command(msg)
        if ok3:
            return await handle_delete(target3, session)

    if is_digest_command(msg):
        return await handle_digest_now()

    if is_summarize_command(msg):
        return await handle_summarize_url(msg)

    return await handle_chat(msg)
