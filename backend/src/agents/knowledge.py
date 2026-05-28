"""Knowledge Agent — save links, summarize URLs, and generate AI digests."""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlparse

import httpx
from loguru import logger
from openai import AsyncOpenAI

from src.agents._base import stub_run
from src.config import get_settings
from src.integrations import ObsidianClient
from src.integrations.knowledge_sources import KnowledgeItem, fetch_rss, search_arxiv, search_tavily

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState

SubIntent = Literal["save_url", "digest_now", "summarize_url", "other"]

URL_RE = re.compile(r"https?://\S+")
SAVE_KEYWORDS = ("save", "bookmark", "read later", "for later")
DIGEST_KEYWORDS = (
    "what's new",
    "whats new",
    "latest",
    "new papers",
    "ai news",
    "new in ai",
    "recent papers",
    "any new",
)
SUMMARIZE_KEYWORDS = ("summarize", "summary", "tldr", "tl;dr", "what does this say")

TO_READ_PATH = "01-Knowledge/To-Read.md"
ARXIV_QUERY = "language models OR LLM OR diffusion"

SYSTEM_PROMPT = """You are the Knowledge Agent. You curate AI/research news for the user,
save articles they want to read, and write daily digests to their Obsidian vault under
01-Knowledge/. Be concise and skip filler."""


def extract_urls(message: str) -> list[str]:
    return URL_RE.findall(message)


def classify_sub_intent(message: str) -> SubIntent:
    lowered = message.lower()
    has_url = bool(extract_urls(message))

    if has_url and any(k in lowered for k in SAVE_KEYWORDS):
        return "save_url"
    if has_url and any(k in lowered for k in SUMMARIZE_KEYWORDS):
        return "summarize_url"
    if not has_url and any(k in lowered for k in DIGEST_KEYWORDS):
        return "digest_now"
    return "other"


async def classify_sub_intent_with_fallback(message: str) -> SubIntent:
    heuristic = classify_sub_intent(message)
    if heuristic != "other":
        return heuristic

    if not extract_urls(message):
        return "other"

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    prompt = (
        "Classify this user request into exactly one label: save_url, summarize_url, or other. "
        "Use save_url only when user asks to save/bookmark/read later. "
        "Use summarize_url when user asks to summarize/tldr/explain a linked page now. "
        "Return one word only."
    )
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model_cheap,
            max_tokens=5,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": message},
            ],
        )
        label = (resp.choices[0].message.content or "").strip().lower()
    except Exception as e:
        logger.warning("Knowledge sub-intent fallback failed: {}", e)
        return "other"

    if label in {"save_url", "summarize_url", "other"}:
        return label  # type: ignore[return-value]
    return "other"


def _short_blurb(text: str, max_len: int = 140) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 1].rstrip() + "..."


def _format_date(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d") if dt else "n/a"


def _domain_from_url(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else (netloc or "web")


async def fetch_url_text(url: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"https://r.jina.ai/{url}", headers={"Accept": "text/plain"})
        response.raise_for_status()
        return response.text[:20000]


async def _extract_article_fields(url: str, article_text: str) -> dict[str, Any]:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    prompt = (
        "Extract metadata for a saved reading item. Return JSON object with keys: "
        "title (string), summary (2-3 sentences), tags (array of up to 4 short tags)."
    )
    resp = await client.chat.completions.create(
        model=settings.openai_model_main,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"URL: {url}\n\nArticle content:\n{article_text}",
            },
        ],
    )
    raw = (resp.choices[0].message.content or "{}").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Article extraction returned non-JSON payload")
        data = {}
    return data


def _format_to_read_entry(
    title: str,
    url: str,
    source: str,
    saved_at: datetime,
    summary: str,
    tags: list[str],
) -> str:
    safe_tags = []
    for tag in tags:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(tag).strip().lower()).strip("-")
        if cleaned:
            safe_tags.append(f"#{cleaned}")
    tags_text = " ".join(safe_tags) if safe_tags else "#reading"
    stamp = saved_at.strftime("%Y-%m-%d %H:%M")
    return (
        "\n\n---\n"
        f"## [{title}]({url})\n"
        f"*{source} · saved {stamp} · {tags_text}*\n\n"
        f"{summary}\n"
    )


async def _save_url(message: str) -> dict:
    urls = extract_urls(message)
    if not urls:
        return await _fallback_stub(message)

    url = urls[0]
    source = _domain_from_url(url)
    title = url
    summary = "Saved for later."
    tags: list[str] = ["reading"]
    try:
        article_text = await fetch_url_text(url)
        parsed = await _extract_article_fields(url, article_text)
        title = str(parsed.get("title") or title).strip() or title
        summary = str(parsed.get("summary") or summary).strip() or summary
        raw_tags = parsed.get("tags") if isinstance(parsed.get("tags"), list) else []
        tags = [str(t) for t in raw_tags][:4] if raw_tags else tags
    except Exception as e:
        logger.warning("Save URL extraction failed for {}: {}", url, e)

    async with ObsidianClient() as client:
        try:
            await client.get_note(TO_READ_PATH)
        except httpx.HTTPStatusError:
            await client.create_note(TO_READ_PATH, "# Reading List\n")

        entry = _format_to_read_entry(
            title=title,
            url=url,
            source=source,
            saved_at=datetime.now(),
            summary=summary,
            tags=tags,
        )
        await client.append_to_note(TO_READ_PATH, entry)

    return {
        "reply": f"Saved '{title}' to To-Read.",
        "obsidian_path": TO_READ_PATH,
    }


async def _summarize_url(message: str) -> dict:
    urls = extract_urls(message)
    if not urls:
        return await _fallback_stub(message)

    url = urls[0]
    source = _domain_from_url(url)
    try:
        article_text = await fetch_url_text(url)
        parsed = await _extract_article_fields(url, article_text)
        title = str(parsed.get("title") or url).strip() or url
        summary = str(parsed.get("summary") or "Could not summarize this URL.").strip()
    except Exception as e:
        logger.warning("Summarize URL failed for {}: {}", url, e)
        title = url
        summary = "I could not fetch this page right now. Try again later."

    reply = f"**{title}**\n\n{summary}\n\n*Source: {source}*"
    return {"reply": reply}


def _dedupe_items(items: list[KnowledgeItem]) -> list[KnowledgeItem]:
    seen: set[str] = set()
    deduped: list[KnowledgeItem] = []
    for item in items:
        key = item.url.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _sort_recent(items: list[KnowledgeItem]) -> list[KnowledgeItem]:
    return sorted(items, key=lambda it: it.published or datetime.min, reverse=True)


def _render_digest_list(items: list[KnowledgeItem]) -> str:
    lines: list[str] = []
    for item in items:
        lines.append(
            f"- **{item.title}** — {_short_blurb(item.summary)} "
            f"(*{item.source} · {_format_date(item.published)}*)"
        )
    return "\n".join(lines)


async def _digest_now() -> dict:
    settings = get_settings()
    rss_task = fetch_rss(settings.rss_feed_list, max_per_feed=5)
    arxiv_task = search_arxiv(ARXIV_QUERY, max_results=10)
    rss_items, arxiv_items = await asyncio.gather(rss_task, arxiv_task)

    merged = _sort_recent(_dedupe_items([*rss_items, *arxiv_items]))[:10]
    if not merged:
        return {"reply": "I couldn't find recent AI updates right now. Please try again in a bit."}
    return {"reply": _render_digest_list(merged)}


async def _rank_items_with_llm(items: list[KnowledgeItem]) -> dict[str, tuple[int, str]]:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    payload = [
        {
            "title": item.title,
            "url": item.url,
            "source": item.source,
            "published": _format_date(item.published),
            "summary": _short_blurb(item.summary, 240),
        }
        for item in items
    ]
    prompt = (
        "Rate these AI updates by interestingness for someone building AI products. "
        "Return JSON object: {\"rankings\": [{\"url\": str, \"score\": int(1-10), "
        "\"reason\": str}]}. Keep reasons concise."
    )

    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model_main,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        raw = (resp.choices[0].message.content or "{}").strip()
        data = json.loads(raw)
    except Exception as e:
        logger.warning("Knowledge ranking failed, using fallback ordering: {}", e)
        return {item.url: (5, _short_blurb(item.summary, 120)) for item in items}

    rankings = data.get("rankings", []) if isinstance(data, dict) else []
    scored: dict[str, tuple[int, str]] = {}
    for row in rankings:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url", "")).strip()
        if not url:
            continue
        try:
            score = int(row.get("score", 5))
        except (TypeError, ValueError):
            score = 5
        reason = _short_blurb(str(row.get("reason", "")).strip() or "Notable update.", 140)
        scored[url] = (max(1, min(score, 10)), reason)
    return scored


def _brief_section(items: list[tuple[KnowledgeItem, int, str]], numbered: bool = True) -> str:
    if not items:
        return "_No items found._\n"
    lines: list[str] = []
    for idx, (item, score, reason) in enumerate(items, start=1):
        prefix = f"{idx}." if numbered else "-"
        lines.append(f"{prefix} [{item.title}]({item.url}) — score {score}")
        lines.append(f"   *{item.source} · {_format_date(item.published)}*")
        lines.append(f"   {reason}")
        lines.append("")
    return "\n".join(lines).rstrip()


async def build_daily_brief() -> str:
    settings = get_settings()
    rss_task = fetch_rss(settings.rss_feed_list, max_per_feed=5)
    arxiv_task = search_arxiv(ARXIV_QUERY, max_results=10)
    tavily_task = search_tavily("AI agents OR LLM evaluation", max_results=5)
    rss_items, arxiv_items, tavily_items = await asyncio.gather(rss_task, arxiv_task, tavily_task)

    combined = _sort_recent(_dedupe_items([*rss_items, *arxiv_items, *tavily_items]))[:30]
    scores = await _rank_items_with_llm(combined)
    ranked = sorted(
        combined,
        key=lambda item: (scores.get(item.url, (5, ""))[0], item.published or datetime.min),
        reverse=True,
    )[:12]

    scored_items = [
        (item, *scores.get(item.url, (5, _short_blurb(item.summary, 120))))
        for item in ranked
    ]
    top_stories = [row for row in scored_items if row[0].source not in {"arXiv", "Tavily"}]
    new_papers = [row for row in scored_items if row[0].source == "arXiv"]
    trending = [row for row in scored_items if row[0].source == "Tavily"]

    now = datetime.now()
    day = now.strftime("%Y-%m-%d")
    brief_path = f"00-Inbox/Daily/{day}-AI-Brief.md"
    lines = [
        f"# AI Brief — {day}",
        "",
        f"*Generated at {now.strftime('%H:%M')}*",
        "",
        "## Top stories",
        "",
        _brief_section(top_stories),
        "",
        "## New papers",
        "",
        _brief_section(new_papers),
    ]

    if settings.tavily_api_key:
        lines.extend(
            [
                "",
                "## Trending searches",
                "",
                _brief_section(trending),
            ]
        )

    content = "\n".join(lines).rstrip() + "\n"
    async with ObsidianClient() as client:
        await client.create_note(brief_path, content)
    logger.info("Knowledge daily brief written to {}", brief_path)
    return brief_path


async def _fallback_stub(message: str) -> dict:
    state: AgentState = {"user_message": message, "attachments": []}
    return await stub_run(state, "knowledge")


async def run(state: AgentState) -> dict:
    message = state.get("user_message", "")
    sub_intent = await classify_sub_intent_with_fallback(message)

    if sub_intent == "save_url":
        return await _save_url(message)
    if sub_intent == "digest_now":
        return await _digest_now()
    if sub_intent == "summarize_url":
        return await _summarize_url(message)
    return await stub_run(state, "knowledge")
