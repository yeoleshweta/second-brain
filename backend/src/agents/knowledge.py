"""Ross — Knowledge Agent.

Handles saving URLs/notes to the reading list, reading list management,
on-demand digests, and building the morning brief. Does NOT fall back
to stub_run — chat-only replies stay in chat, nothing leaks to the inbox.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx
from loguru import logger
from openai import AsyncOpenAI
from sqlmodel import Session

from src.config import get_settings
from src.integrations import ObsidianClient
from src.integrations.book_discovery import (
    build_oceanofpdf_book_item,
    format_book_not_found_alternatives,
)
from src.integrations.book_download_search import search_web_book_pdf_links
from src.integrations.gutenberg import (
    BookResult,
    book_has_download,
    get_gutenberg_book,
    search_gutenberg_broad,
)
from src.integrations.image_caption import describe_image
from src.integrations.knowledge_sources import (
    GitHubProfile,
    KnowledgeItem,
    balance_items_by_tag,
    extract_topic_tags_from_message,
    fetch_github_profile,
    fetch_rss_sources,
    resolve_feed_sources,
    search_arxiv,
    search_openai_web,
    search_tavily,
    search_tavily_with_options,
)
from src.integrations.librivox import search_librivox
from src.integrations.oceanofpdf import OceanOfPdfMatch, oceanofpdf_search_match, resolve_oceanofpdf
from src.integrations.open_library import search_open_library
from src.services import pending_actions, practice, usage, user_config
from src.services import reading_content as rc
from src.services import reading_list as rl
from src.services import vault_files as vf
from src.services import vocabulary as vocab_service
from src.storage import ReadingListItem, get_session, init_db
from src.storage.models import ItemKind, ItemStatus

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState

# ── Constants ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Ross, the knowledge curator in a personal AI second-brain app.
You help the user save articles, manage their reading list, and stay current on AI news.
Be friendly, concise, and mildly nerdy. Use second person ("your reading list").
When uncertain, ask rather than guess. Do not pretend to have feelings."""

ROSS_CHAT_SYSTEM = (
    "You are Ross Geller from Friends — reimagined as the user's personal "
    "librarian in their second-brain app.\n\n"
    "Voice (stay in character, but be helpful):\n"
    "- Earnest, warm, a little nerdy. You get genuinely excited about books, "
    "research, and learning — the way Ross gets about dinosaurs.\n"
    "- Occasional paleontology nod or precise \"Actually…\" when correcting "
    "something useful. Light awkward charm, not mean.\n"
    "- Short bursts of enthusiasm (\"Oh! Yes!\" / \"Okay so—\") then deliver "
    "the useful bit. Never full sitcom riffs every message.\n"
    "- You care about getting facts right. If something is copyrighted or "
    "not in the public domain, say so plainly and point to legal options.\n\n"
    "Actions you CAN do in chat (user must ask explicitly — the app handles the save):\n"
    "- Save articles, blog posts, and URLs to the reading list: "
    "\"save this https://…\", paste a link, or \"add this article to my reading list\".\n"
    "- Download books: \"download [title]\" · List: \"show my reading list\".\n"
    "- When someone shares a link they want kept, encourage a save phrase — "
    "don't say you cannot save links.\n"
    "- Never invent reading-list items or claim you saved something unless "
    "the app confirmed it (🪄 Saved…).\n\n"
    "Style: second person, 2–5 sentences, conversational. Emoji rarely (📚 🦕 ok)."
)

ARXIV_QUERY = "language models OR LLM OR diffusion OR agent"
TO_READ_DIR = "01-Knowledge/To-Read"
ARCHIVE_DIR = "01-Knowledge/Archive"
NOTES_DIR = "01-Knowledge/Notes"
PDF_DIR = "01-Knowledge/PDFs"
BOOKS_DIR = "01-Knowledge/Books"
VOCAB_DIR = "01-Knowledge/Vocabulary"

# ── Intent patterns ────────────────────────────────────────────────────────────

SAVE_RE = re.compile(
    r"\b("
    r"save in notes|save this|save it|"
    r"save to (?:notes|list|reading list)|"
    r"save (?:this |that |the )?(?:article|link|url|page|post|blog|story|paper)|"
    r"add (?:this |that |the )?(?:article|link|url|page|post|blog|story|paper)|"
    r"bookmark(?: this| it| that)?|"
    r"add to (?:reading list|notes|list)|"
    r"remember this|file this|"
    r"download pdf|save pdf|"
    r"save.*for me to read|"
    r"save (?:this )?(?:pdf|document|file|paper|doc)|"
    r"keep(?: this| that)?(?: (?:article|link|url|page|post|blog|story))?|"
    r"store this link"
    r")\b",
    re.IGNORECASE,
)
CONTEXTUAL_SAVE_RE = re.compile(
    r"\b(save|add|bookmark|keep|store)\s+(it|this|that|the (article|link|page|post|blog|story|paper))\b|"
    r"\b(add|save)\s+(it|this|that)\s+(to|on|into)\s+(my\s+)?(reading list|list)\b",
    re.IGNORECASE,
)
SAVE_LINK_HINT_RE = re.compile(
    r"\b(article|link|url|page|post|blog|story|paper)\b",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://\S+")

LIST_RE = re.compile(
    r"\b(show (my )?reading list|what'?s in (my )?reading list)\b|"
    r"^\s*reading list\s*$",
    re.IGNORECASE,
)
ADD_TO_LIST_RE = re.compile(
    r"\b(add|download|get|save|fetch).{0,40}\b(to|on|into)\s+(my\s+)?(reading list|list)\b",
    re.IGNORECASE,
)
HELP_READ_BOOK_RE = re.compile(
    r"\b(?:help me (?:read|get|find|download)|can you help me read|i want to read|want to read)\s+(.{2,80}?)\s*[?.!]*$",
    re.IGNORECASE,
)
CONTEXTUAL_BOOK_RE = re.compile(
    r"\b(download|get|fetch|add).{0,30}\b(reading list|my list)\b|"
    r"\b(download|get|fetch)\s+(it|this|that|same one|the book)\b",
    re.IGNORECASE,
)
LIST_FILTERED_RE = re.compile(r"\b(filtered by|tag)\s+([a-z0-9\-_ ]+)$", re.IGNORECASE)
LIST_READ_WEEK_RE = re.compile(r"\bwhat have i read (this|last) week\b", re.IGNORECASE)
MARK_READ_RE = re.compile(
    r"\b(mark .+ as read|finished reading .+|i (just )?finished .+|done with .+)\b",
    re.IGNORECASE,
)
PROGRESS_RE = re.compile(
    r"(\d+)\s*%\s+(.+)|i'?m\s+(\d+)\s*%\s+(through|done with)\s+(.+)|(\d+)\s+percent\s+of\s+(.+)",
    re.IGNORECASE,
)
DELETE_RE = re.compile(
    r"\b(delete|remove)\s+(.+?)(\s+from\s+(my\s+)?list)?\b",
    re.IGNORECASE,
)
QUERY_RE = re.compile(
    r"\b(what do i know about|have i read anything on|anything in my notes about)\s+(.+)$",
    re.IGNORECASE,
)
SUGGEST_RE = re.compile(
    (
        r"\b(suggest (me )?(something|few things|a few things|3 things)( to read)?( today)?|"
        r"what should i read( today| next)?|"
        r"give me something interesting|"
        r"recommend (something|articles|papers|reads)( to read)?( today)?)\b"
    ),
    re.IGNORECASE,
)
SUGGEST_TIME_RE = re.compile(r"\b(\d+)\s*min(?:ute)?s?\s+read\b", re.IGNORECASE)
PRACTICE_LOG_RE = re.compile(
    r"\b(practiced|practice|did|coded)\s+(.+?)\s+(for\s+)?(\d+)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours)\b",
    re.IGNORECASE,
)
PRACTICE_STATUS_RE = re.compile(
    r"\b(how'?s my practice going|how'?s my practice|did i practice today|what'?s my streak)\b",
    re.IGNORECASE,
)
SET_READING_GOAL_RE = re.compile(r"\bset reading goal to\s+(\d+)\s*min", re.IGNORECASE)
PAUSE_NUDGES_TODAY_RE = re.compile(r"\bpause nudges for today\b", re.IGNORECASE)
PAUSE_NUDGES_WEEK_RE = re.compile(r"\bpause nudges for (the )?week\b", re.IGNORECASE)
RESUME_NUDGES_RE = re.compile(r"\bresume nudges\b", re.IGNORECASE)
ADD_SKILL_RE = re.compile(r"\b(add skill|track)\s+([a-z0-9\-_ ]+)$", re.IGNORECASE)
STOP_SKILL_RE = re.compile(r"\b(stop tracking)\s+([a-z0-9\-_ ]+)$", re.IGNORECASE)
QUIET_HOURS_RE = re.compile(r"\bquiet hours\s+(\d{1,2})\s+to\s+(\d{1,2})\b", re.IGNORECASE)
CLEAR_LIST_RE = re.compile(r"\bclear my reading list\b", re.IGNORECASE)
CONFIRM_CLEAR_RE = re.compile(r"\bconfirm clear all\b", re.IGNORECASE)
STOP_NAGGING_RE = re.compile(
    r"\b(stop nagging|you'?re annoying|shut up about|mute)\b",
    re.IGNORECASE,
)
DIGEST_RE = re.compile(
    r"\b("
    r"what'?s new|whats new|any new (?:in|on|about)|"
    r"new papers|recent papers|"
    r"ai news|new in ai|new finds|fresh items"
    r")\b",
    re.IGNORECASE,
)
RESEARCH_RE = re.compile(
    r"\b("
    r"research papers?|find papers|search papers|find me papers|"
    r"arxiv|academic papers?|journal articles?|scientific papers?|"
    r"find articles|search articles|articles on|papers on|"
    r"read papers|paper on|article on|peer.?reviewed|"
    r"recommend papers|paper recommendations"
    r")\b",
    re.IGNORECASE,
)
MAX_SUGGEST_ITEMS = 3
SUMMARIZE_RE = re.compile(
    r"\b(summarize|summary|tldr|tl;dr|what does this say)\b",
    re.IGNORECASE,
)
FIND_BOOK_RE = re.compile(
    r"\b("
    r"find (me )?(a )?free (book|books|ebook|ebooks|copy|copies)|"
    r"free books (on|about)|any free books|search (for )?books (on|about)|"
    r"project gutenberg|gutenberg books"
    r")\b",
    re.IGNORECASE,
)
DOWNLOAD_BOOK_RE = re.compile(
    r"\b("
    r"(download|get|save|fetch)\b.+\b(book|ebook|audiobook)\b|"
    r"(download|get|save|fetch)\b.+\b(by|from gutenberg)\b|"
    r"free copy of"
    r")\b",
    re.IGNORECASE,
)
# "download atomic habits" / "get dune" — title only, no word "book"
SIMPLE_DOWNLOAD_RE = re.compile(
    r"^\s*(download|get|fetch)\s+(?:me\s+)?(?:the\s+)?(.{2,100})\s*$",
    re.IGNORECASE,
)
NON_BOOK_DOWNLOAD_RE = re.compile(
    r"\b(this|that|it|article|url|page|file|pdf|note|notes|image|photo)\b",
    re.IGNORECASE,
)
LOG_VOCAB_RE = re.compile(
    r"\b(log vocab(?:ulary)?|save vocab(?:ulary)?|add vocab(?:ulary)?|learned (?:the )?word)\b",
    re.IGNORECASE,
)
VOCAB_LINE_RE = re.compile(
    r"^(?P<word>[A-Za-z][A-Za-z\-']{1,40})\s*[-–—:]\s*(?P<def>.+)$",
)
LIST_VOCAB_RE = re.compile(
    r"\b(my vocab(?:ulary)?|vocabulary list|words i(?:'ve| have) learned)\b",
    re.IGNORECASE,
)
KNOWLEDGE_STATS_RE = re.compile(
    r"\b(knowledge (?:base )?stats|knowledge progress|reading progress|what have i learned)\b",
    re.IGNORECASE,
)
APPLE_BOOKS_RE = re.compile(
    r"\b("
    r"apple books|books app|"
    r"what am i reading|currently reading|reading now|books in progress|"
    r"my book library|list my books|library stats|reading stats|"
    r"my highlights|book highlights|recent highlights|"
    r"highlights from|annotations from|notes from|"
    r"search (?:my )?books|do i have .{2,60} in (?:my )?books"
    r")\b",
    re.IGNORECASE,
)

SubIntent = str

_VAGUE_BOOK_QUERIES = frozenset({
    "my reading list",
    "reading list",
    "the reading list",
    "it",
    "this",
    "that",
    "the book",
    "same one",
    "same book",
    "and add to my reading list",
    "to my reading list",
    "add to my reading list",
    "and",
    "okay",
    "add this",
    "add that",
    "this to the list",
    "that to the list",
    "add this to the list",
    "add that to the list",
})


def _chat_turns(history: list[dict] | None) -> list[dict]:
    return history or []


def _is_vague_book_query(query: str) -> bool:
    normalized = query.lower().strip(" .,-")
    if normalized in _VAGUE_BOOK_QUERIES:
        return True
    if re.fullmatch(
        r"(and )?(add( it)?|download( it)?) to (my )?(reading )?list",
        normalized,
    ):
        return True
    return len(normalized) < 2


def _book_title_from_assistant(text: str) -> str | None:
    for pat in (
        r"'([^']{2,80})'\s+by\s+",
        r"\*\*([^*]{2,80})\*\*",
        r"「([^」]{2,80})」",
    ):
        m = re.search(pat, text)
        if m:
            title = m.group(1).split(" by ")[0].strip()
            skip = {"ocean of pdf", "no free in-app download", "legal options"}
            if title and title.lower() not in skip:
                return title
    return None


def _resolve_book_query(msg: str, history: list[dict] | None = None) -> str:
    """Extract book title from message, or from recent chat if follow-up is vague."""

    def _title_from_history() -> str | None:
        for turn in reversed(_chat_turns(history)[-10:]):
            content = (turn.get("content") or "").strip()
            if not content:
                continue
            role = turn.get("role", "")
            if role == "user":
                help_u = HELP_READ_BOOK_RE.search(content)
                if help_u:
                    candidate = help_u.group(1).strip(" .,-?!")
                    if candidate and not _is_vague_book_query(candidate):
                        return candidate
                candidate = _extract_book_query(content)
                if candidate and not _is_vague_book_query(candidate):
                    return candidate
            elif role == "assistant":
                from_assistant = _book_title_from_assistant(content)
                if from_assistant and not _is_vague_book_query(from_assistant):
                    return from_assistant
        return None

    help_m = HELP_READ_BOOK_RE.search(msg)
    if help_m:
        title = help_m.group(1).strip(" .,-?!")
        if title and not _is_vague_book_query(title):
            return title

    if CONTEXTUAL_BOOK_RE.search(msg) or (
        re.search(r"\b(download|get|fetch|add)\b", msg, re.I)
        and re.search(r"\breading list\b", msg, re.I)
    ):
        from_history = _title_from_history()
        if from_history:
            return from_history

    direct = _extract_book_query(msg)
    if direct and not _is_vague_book_query(direct):
        return direct

    from_history = _title_from_history()
    if from_history:
        return from_history

    return direct if direct and not _is_vague_book_query(direct) else ""


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


def _log_openai_usage(response: Any, model: str, route: str) -> None:
    prompt_tokens = int(getattr(getattr(response, "usage", None), "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(getattr(response, "usage", None), "completion_tokens", 0) or 0)
    try:
        with next(get_session()) as session:
            usage.log(
                session,
                agent="ross",
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                route=route,
            )
    except Exception as exc:
        logger.debug("Usage log skipped: {}", exc)


# ── URL fetching ───────────────────────────────────────────────────────────────


async def fetch_url_text(url: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(f"https://r.jina.ai/{url}", headers={"Accept": "text/plain"})
        r.raise_for_status()
        return r.text[:20_000]


def _wants_pdf_download(msg: str) -> bool:
    lowered = msg.lower()
    if re.search(r"\bdownload pdf\b|\bsave pdf\b", lowered):
        return True
    has_save = re.search(r"\b(download|save)\b", lowered)
    has_pdf = re.search(r"\b(pdf|paper)\b", lowered)
    return bool(has_save and has_pdf)


def _looks_like_failed_fetch(title: str, text: str) -> bool:
    t = title.strip().lower()
    if t.startswith("404") or "page not found" in t:
        return True
    head = text[:300].lower()
    return "404" in head and "not found" in head


def _should_save_as_pdf(url: str, *, kind: str = "url", pdf_url: str | None = None) -> bool:
    if pdf_url:
        return True
    return rc.is_probable_pdf_url(url)


async def _attach_readable_content(
    session: Session,
    item: ReadingListItem,
    *,
    url: str | None = None,
    pdf_url: str | None = None,
    note_body: str | None = None,
    pdf_src: Path | None = None,
    prefer_pdf: bool = False,
) -> tuple[ReadingListItem, str]:
    """Fetch or copy readable content onto a saved reading-list item."""
    if item.id is None:
        return item, ""

    content_note = ""
    content_path: str | None = None

    if pdf_src and pdf_src.exists():
        content_path = rc.copy_pdf(item.id, pdf_src)
        item.kind = ItemKind.PDF
        content_note = " Tap **Read** in your Reading list to open the PDF."
        if not content_path:
            text, _ = _extract_pdf_text(pdf_src)
            if text.strip():
                content_path = rc.write_markdown(item.id, f"# {item.title}\n\n{text}")
                content_note = " Saved extracted text — tap **Read** in your Reading list."
    elif prefer_pdf or pdf_url:
        pdf_candidates: list[str] = []
        if pdf_url:
            pdf_candidates.append(pdf_url)
        if url and url not in pdf_candidates:
            pdf_candidates.append(url)
        for candidate in pdf_candidates:
            content_path = await rc.download_pdf(item.id, candidate)
            if content_path:
                item.kind = ItemKind.PDF
                content_note = " PDF saved — tap **Read** in your Reading list."
                break
        if not content_path and url and not rc.is_probable_pdf_url(url):
            try:
                text = await fetch_url_text(url)
                if not _looks_like_failed_fetch(item.title, text) and not rc.is_jina_pdf_placeholder(
                    text
                ):
                    md = f"# {item.title}\n\nSource: {url}\n\n---\n\n{text}"
                    content_path = rc.write_markdown(item.id, md)
                    content_note = (
                        " Couldn't download the PDF — saved page text instead. "
                        "Open the original link for the full paper."
                    )
            except Exception as exc:
                logger.warning("Fallback fetch failed for {}: {}", url, exc)
                content_note = " Link saved; PDF download failed — try opening the URL."
        elif not content_path:
            content_note = " PDF couldn't be downloaded — open the link in Safari."
    elif url:
        try:
            text = await fetch_url_text(url)
            if _looks_like_failed_fetch(item.title, text):
                content_note = " Couldn't fetch the page — link saved; try opening externally."
            else:
                md = f"# {item.title}\n\nSource: {url}\n\n---\n\n{text}"
                content_path = rc.write_markdown(item.id, md)
                content_note = " Full article saved — tap **Read** in your Reading list."
        except Exception as exc:
            logger.warning("Content fetch failed for {}: {}", url, exc)
            content_note = " Link saved; content fetch failed — try **Read** later or open the URL."
    elif note_body:
        md = f"# {item.title}\n\n{note_body.strip()}"
        content_path = rc.write_markdown(item.id, md)
        content_note = " Note saved — tap **Read** in your Reading list."

    if content_path:
        item.content_path = content_path
        session.add(item)
        session.commit()
        session.refresh(item)

    return item, content_note


def _resolve_uploaded_file(file_id: str) -> Path | None:
    settings = get_settings()
    upload_dir = Path(settings.data_dir) / "uploads"
    if not upload_dir.exists():
        return None
    matches = list(upload_dir.glob(f"{file_id}.*"))
    return matches[0] if matches else None


def _attachment_filename(att: dict) -> str:
    return str(att.get("filename") or att.get("name") or "").strip()


def _infer_attachment_type(att: dict) -> str:
    """Return pdf | text | docx | document | image | unknown."""
    media = (att.get("media_type") or "").lower()
    name = _attachment_filename(att).lower()
    ext = Path(name).suffix if name else ""

    if "pdf" in media or ext == ".pdf":
        return "pdf"
    if media.startswith("text/") or ext in {".txt", ".md", ".markdown"}:
        return "text"
    if ext in {".docx", ".doc"} or "wordprocessingml" in media or ext == ".doc":
        return "docx"
    if media.startswith("image/") or ext in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        return "image"
    if ext in {".rtf", ".csv", ".json"}:
        return "document"
    return "unknown"


def _is_reading_attachment(att: dict) -> bool:
    return _infer_attachment_type(att) in {"pdf", "text", "docx", "document"}


def _has_any_attachment(attachments: list[dict] | None) -> bool:
    return bool(attachments)


def _find_reading_attachment(attachments: list[dict]) -> dict | None:
    for att in attachments:
        if _is_reading_attachment(att):
            return att
    return None


def _extract_docx_text(path: Path, max_chars: int = 30_000) -> str:
    """Extract plain text from .docx using stdlib only."""
    import zipfile
    from xml.etree import ElementTree

    try:
        with zipfile.ZipFile(path) as zf:
            xml_bytes = zf.read("word/document.xml")
    except Exception as exc:
        logger.warning("DOCX read failed for {}: {}", path, exc)
        return ""

    root = ElementTree.fromstring(xml_bytes)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    parts = [node.text for node in root.findall(".//w:t", ns) if node.text]
    text = "\n".join(parts).strip()
    return text[:max_chars]


def _read_uploaded_text(path: Path, max_chars: int = 30_000) -> str:
    ext = path.suffix.lower()
    if ext == ".docx":
        return _extract_docx_text(path, max_chars=max_chars)
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except Exception as exc:
        logger.warning("Text read failed for {}: {}", path, exc)
        return ""


def _extract_pdf_text(path: Path, max_chars: int = 30_000) -> tuple[str, int]:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(str(path))
        pages = len(reader.pages)
        chunks: list[str] = []
        for page in reader.pages[: min(pages, 20)]:
            chunks.append((page.extract_text() or "").strip())
            if sum(len(c) for c in chunks) >= max_chars:
                break
        text = "\n".join(chunks)
        return text[:max_chars], pages
    except Exception as exc:
        logger.warning("PDF text extraction failed for {}: {}", path, exc)
        return "", 0


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
    _log_openai_usage(resp, settings.openai_model_main, "save_extract")
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
    _log_openai_usage(resp, settings.openai_model_cheap, "note_title")
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
    if item.kind == ItemKind.NOTE:
        path = f"{NOTES_DIR}/{slug}.md"
    elif item.kind == ItemKind.PDF:
        path = f"{PDF_DIR}/{slug}.md"
    elif item.kind in {ItemKind.EBOOK, ItemKind.AUDIOBOOK}:
        path = f"{BOOKS_DIR}/{slug}.md"
    else:
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


def _url_from_chat_history(history: list[dict] | None) -> str | None:
    for turn in reversed(_chat_turns(history)[-12:]):
        content = (turn.get("content") or "").strip()
        urls = _extract_urls(content)
        if urls:
            return urls[0]
    return None


def is_bare_url_save(msg: str) -> bool:
    """Single pasted link (optionally with a short note) → save to reading list."""
    urls = _extract_urls(msg)
    if len(urls) != 1:
        return False
    remainder = URL_RE.sub("", msg).strip()
    if "?" in remainder:
        return False
    if re.search(
        r"\b(what|how|why|when|where|explain|summarize|tell me|describe|compare)\b",
        remainder,
        re.IGNORECASE,
    ):
        return False
    return len(remainder) < 100


def is_contextual_save_request(msg: str, history: list[dict] | None = None) -> bool:
    """Follow-up: save the link Ross or the user mentioned earlier."""
    if not CONTEXTUAL_SAVE_RE.search(msg) and not (
        re.search(r"\b(add|save)\b", msg, re.I)
        and re.search(r"\b(reading list|for later)\b", msg, re.I)
        and SAVE_LINK_HINT_RE.search(msg)
    ):
        return False
    if _extract_urls(msg):
        return True
    if SAVE_LINK_HINT_RE.search(msg) and _url_from_chat_history(history):
        return True
    if CONTEXTUAL_SAVE_RE.search(msg) and _url_from_chat_history(history):
        return True
    return False


def is_save_link_request(msg: str, history: list[dict] | None = None) -> bool:
    if is_save_command(msg):
        return True
    if is_bare_url_save(msg):
        return True
    if is_contextual_save_request(msg, history):
        return True
    return False


def is_list_command(msg: str) -> bool:
    if ADD_TO_LIST_RE.search(msg):
        return False
    if CONTEXTUAL_BOOK_RE.search(msg):
        return False
    if is_help_read_book_command(msg):
        return False
    return bool(LIST_RE.search(msg))


def is_help_read_book_command(msg: str) -> bool:
    return bool(HELP_READ_BOOK_RE.search(msg))


def is_contextual_book_request(msg: str, history: list[dict] | None = None) -> bool:
    if not CONTEXTUAL_BOOK_RE.search(msg) and not (
        re.search(r"\b(download|get|fetch|add)\b", msg, re.I)
        and re.search(r"\breading list\b", msg, re.I)
    ):
        return False
    return bool(_resolve_book_query(msg, history)) and not _is_vague_book_query(
        _resolve_book_query(msg, history)
    )


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
    if m.group(3):
        return True, int(m.group(3)), m.group(5).strip()
    if m.group(6):
        return True, int(m.group(6)), m.group(7).strip()
    return False, 0, ""


def is_delete_command(msg: str) -> tuple[bool, str]:
    m = DELETE_RE.search(msg)
    if not m:
        return False, ""
    return True, m.group(2).strip()


def is_digest_command(msg: str) -> bool:
    return bool(DIGEST_RE.search(msg))


def is_research_command(msg: str) -> bool:
    if RESEARCH_RE.search(msg):
        return True
    has_paper = bool(re.search(r"\b(papers?|articles?)\b", msg, re.IGNORECASE))
    has_book = bool(re.search(r"\b(books?|ebooks?|audiobooks?|gutenberg)\b", msg, re.IGNORECASE))
    return has_paper and not has_book


def is_summarize_command(msg: str) -> bool:
    return bool(_extract_urls(msg)) and bool(SUMMARIZE_RE.search(msg))


def is_query_command(msg: str) -> tuple[bool, str]:
    m = QUERY_RE.search(msg)
    if not m:
        return False, ""
    return True, m.group(2).strip()


def is_suggest_command(msg: str) -> tuple[bool, int | None]:
    if not SUGGEST_RE.search(msg):
        return False, None
    t = SUGGEST_TIME_RE.search(msg)
    return True, int(t.group(1)) if t else None


def is_practice_log_command(msg: str) -> tuple[bool, str, int]:
    m = PRACTICE_LOG_RE.search(msg)
    if not m:
        return False, "", 0
    skill = m.group(2).strip().lower()
    qty = int(m.group(4))
    unit = m.group(5).lower()
    minutes = qty * 60 if unit.startswith("h") else qty
    return True, skill, minutes


def is_practice_status_command(msg: str) -> bool:
    return bool(PRACTICE_STATUS_RE.search(msg))


def _extract_book_query(msg: str) -> str:
    """Pull a book title/topic out of natural language."""
    from src.integrations.gutenberg import BOOK_QUERY_ALIASES

    if re.match(r"^\s*add\s+(this|that|it)\b", msg, re.IGNORECASE):
        return ""

    quoted = re.search(r"['\"]([^'\"]{2,100})['\"]", msg)
    if quoted:
        return quoted.group(1).strip()

    for keyword in sorted(BOOK_QUERY_ALIASES.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(keyword)}\b", msg, re.IGNORECASE):
            return keyword

    m = re.search(
        r"(?:download|get|save|fetch|find|search for|free copy of|free books?(?: on| about)?)"
        r"\s+(.+)$",
        msg,
        re.IGNORECASE,
    )
    raw = (m.group(1) if m else msg).strip()

    noise = re.compile(
        r"\b("
        r"can you|could you|please|for me|in the same context|search and|download and|"
        r"find and|look up|help me|i want|i need|to read|and save|same context|"
        r"add to (my )?(reading list|list)|to (my )?(reading list|list)"
        r")\b",
        re.IGNORECASE,
    )
    raw = noise.sub(" ", raw)
    raw = re.sub(r"\b(from gutenberg|gutenberg|open library|librivox)\b", " ", raw, flags=re.I)
    raw = re.sub(r"[?.!,;:]+$", "", raw)
    raw = re.sub(r"\s+", " ", raw).strip(" .,-")

    if len(raw) >= 2:
        return raw
    return ""


def _is_likely_book_title(query: str) -> bool:
    if _is_vague_book_query(query):
        return False
    normalized = query.lower().strip()
    if re.match(r"^(add|save|this|that|it|the)\b", normalized):
        return False
    if re.search(r"\b(papers?|articles?|research|journal|arxiv)\b", normalized):
        return False
    words = [w for w in re.sub(r"[^a-z0-9\s'-]", " ", normalized).split() if len(w) > 1]
    if len(words) >= 2:
        return True
    from src.integrations.gutenberg import BOOK_QUERY_ALIASES

    if normalized in BOOK_QUERY_ALIASES:
        return True
    return len(query.strip()) >= 3 and len(words) == 1


def is_download_book_command(msg: str) -> bool:
    if is_research_command(msg) and not re.search(
        r"\b(books?|ebooks?|audiobooks?)\b", msg, re.IGNORECASE
    ):
        return False
    if is_help_read_book_command(msg):
        return True
    if DOWNLOAD_BOOK_RE.search(msg):
        return True
    m = SIMPLE_DOWNLOAD_RE.match(msg.strip())
    if not m:
        return False
    tail = m.group(2).strip()
    if NON_BOOK_DOWNLOAD_RE.search(tail):
        return False
    return _is_likely_book_title(tail)


def is_find_book_command(msg: str) -> bool:
    return bool(FIND_BOOK_RE.search(msg)) and not is_download_book_command(msg)


def is_log_vocab_command(msg: str) -> bool:
    return bool(LOG_VOCAB_RE.search(msg))


def is_list_vocab_command(msg: str) -> bool:
    return bool(LIST_VOCAB_RE.search(msg))


def is_apple_books_command(msg: str) -> bool:
    return bool(APPLE_BOOKS_RE.search(msg))


def is_knowledge_stats_command(msg: str) -> bool:
    return bool(KNOWLEDGE_STATS_RE.search(msg))


def classify_sub_intent(
    msg: str,
    attachments: list[dict] | None = None,
    history: list[dict] | None = None,
) -> SubIntent:
    lowered = msg.strip().lower()
    attachments = attachments or []

    if STOP_NAGGING_RE.search(lowered):
        return "pause_nudges"
    if SET_READING_GOAL_RE.search(lowered):
        return "set_reading_goal"
    if PAUSE_NUDGES_TODAY_RE.search(lowered) or PAUSE_NUDGES_WEEK_RE.search(lowered):
        return "pause_nudges"
    if RESUME_NUDGES_RE.search(lowered):
        return "resume_nudges"
    if ADD_SKILL_RE.search(lowered):
        return "add_skill"
    if STOP_SKILL_RE.search(lowered):
        return "remove_skill"
    if QUIET_HOURS_RE.search(lowered):
        return "set_quiet_hours"
    if CLEAR_LIST_RE.search(lowered):
        return "clear_list"
    if CONFIRM_CLEAR_RE.search(lowered):
        return "confirm_clear_list"

    if is_save_link_request(msg, history):
        return "save"

    if is_download_book_command(msg):
        return "download_book"
    if is_contextual_book_request(msg, history):
        return "download_book"
    if is_research_command(msg):
        return "research_search"
    if is_apple_books_command(msg):
        return "apple_books"
    if is_topic_search_command(msg, history):
        return "topic_search"
    if is_find_book_command(msg):
        return "find_book"
    if is_log_vocab_command(msg):
        return "log_vocab"
    if is_list_vocab_command(msg):
        return "list_vocab"
    if is_knowledge_stats_command(msg):
        return "knowledge_stats"

    # Attachment-first: any file/image/PDF sent alone or with save intent → Ross captures it.
    if _has_any_attachment(attachments):
        if not lowered or is_save_command(lowered) or is_summarize_command(lowered):
            return "save"

    if is_save_command(lowered):
        return "save"
    if is_list_command(lowered) or LIST_READ_WEEK_RE.search(lowered):
        return "list"
    if is_mark_command(lowered)[0]:
        return "mark_read"
    if is_progress_command(lowered)[0]:
        return "update_progress"
    if is_delete_command(lowered)[0]:
        return "delete"
    if is_query_command(lowered)[0]:
        return "query"
    if is_suggest_command(lowered)[0]:
        return "suggest"
    if is_practice_log_command(lowered)[0]:
        return "log_practice"
    if is_practice_status_command(lowered):
        return "practice_status"
    if is_digest_command(lowered):
        return "digest_now"
    if is_summarize_command(lowered):
        return "summarize_url"
    return "chat"


# ── Handlers ───────────────────────────────────────────────────────────────────


async def _handle_uploaded_document_save(
    session: Session,
    att: dict,
    label: str,
) -> dict:
    """Save an uploaded PDF, text file, or Word doc to the reading list."""
    file_id = att.get("file_id")
    src = _resolve_uploaded_file(str(file_id)) if file_id else None
    att_type = _infer_attachment_type(att)

    if not src or not src.exists():
        return {
            "reply": (
                "Ross: I couldn't find the uploaded file. "
                "Attach it again, then send **save in notes** (or send the file with no message)."
            )
        }

    title = label.strip() or src.stem or "Uploaded document"
    summary: str | None = None
    tags = ""
    pages = 0
    kind = ItemKind.PDF if att_type == "pdf" else ItemKind.NOTE
    source = att_type if att_type != "unknown" else "document"

    if att_type == "pdf":
        text, pages = _extract_pdf_text(src)
        try:
            extract_input = text or title
            parsed = await _extract_article_fields(src.name, extract_input)
            title = str(parsed.get("title") or title).strip() or src.stem
            summary = str(parsed.get("summary") or "").strip() or None
            tags = ",".join(str(t) for t in (parsed.get("tags") or [])[:4])
        except Exception:
            title = title or src.stem
    else:
        text = _read_uploaded_text(src)
        if text.strip():
            try:
                parsed = await _extract_article_fields(src.name, text[:8000])
                title = str(parsed.get("title") or title).strip() or src.stem
                summary = str(parsed.get("summary") or "").strip() or None
                tags = ",".join(str(t) for t in (parsed.get("tags") or [])[:4])
            except Exception:
                title = title or src.stem
        else:
            title = title or src.stem

    item = rl.add(
        session,
        url=None,
        title=title,
        summary=summary,
        source=source,
        kind=kind,
        tags=tags,
    )
    if item is None:
        return {"reply": f"You already saved '{title}'."}

    content_note = ""
    if att_type == "pdf":
        item, content_note = await _attach_readable_content(session, item, pdf_src=src)
    else:
        body = _read_uploaded_text(src)
        md = f"# {title}\n\n{body or '(No extractable text in this file.)'}"
        item.content_path = rc.write_markdown(item.id, md)
        if att_type == "docx":
            rc.copy_document(item.id, src)
        item.kind = ItemKind.NOTE
        session.add(item)
        session.commit()
        session.refresh(item)
        content_note = " Tap **Read** in your Reading list."

    mirror_path = None
    try:
        async with ObsidianClient() as obsidian:
            mirror_path = await _write_mirror(item, obsidian)
        item.mirror_path = mirror_path
        session.add(item)
        session.commit()
    except Exception as e:
        logger.warning("Mirror write failed: {}", e)

    extra = f" ({pages} pages)" if att_type == "pdf" and pages else ""
    capture_path: str | None = None
    vault_note = ""
    try:
        _, capture_path = await vf.store_file_in_vault(
            src,
            title=title,
            summary=summary,
            user_note=label.strip(),
            tags=tags,
        )
        vault_note = f" Also filed in Obsidian: `{capture_path}`."
    except Exception as e:
        logger.warning("Vault file copy failed for {}: {}", title, e)

    return {
        "reply": f"🪄 Saved '{title}' ({source}){extra}.{content_note}{vault_note}",
        "obsidian_path": mirror_path or capture_path,
    }


async def _handle_uploaded_image_save(
    session: Session,
    att: dict,
    label: str,
) -> dict:
    file_id = att.get("file_id")
    src = _resolve_uploaded_file(str(file_id)) if file_id else None
    if not src or not src.exists():
        return {"reply": "Ross: couldn't find that image — try attaching it again."}

    title = label.strip() or src.stem or "Image"
    summary = await describe_image(src, user_hint=label)
    try:
        _, capture_path = await vf.store_file_in_vault(
            src,
            title=title,
            summary=summary,
            user_note=label.strip(),
        )
        return {
            "reply": f"🪄 Saved image to Obsidian `{capture_path}`.",
            "obsidian_path": capture_path,
        }
    except Exception as e:
        logger.warning("Image vault save failed: {}", e)
        return {"reply": f"Ross: couldn't save image to Obsidian — {e}"}


async def _handle_generic_file_save(
    session: Session,
    att: dict,
    label: str,
) -> dict:
    file_id = att.get("file_id")
    src = _resolve_uploaded_file(str(file_id)) if file_id else None
    if not src or not src.exists():
        return {"reply": "Ross: couldn't find that file — try attaching it again."}

    name = _attachment_filename(att) or src.name
    title = label.strip() or src.stem or name
    try:
        _, capture_path = await vf.store_file_in_vault(
            src,
            title=title,
            summary=f"Captured file: `{name}`",
            user_note=label.strip(),
        )
        return {
            "reply": f"🪄 Saved `{name}` to Obsidian `{capture_path}`.",
            "obsidian_path": capture_path,
        }
    except Exception as e:
        logger.warning("Generic vault save failed: {}", e)
        return {"reply": f"Ross: couldn't save file to Obsidian — {e}"}


async def _handle_attachments_save(
    session: Session,
    attachments: list[dict],
    label: str,
) -> dict:
    replies: list[str] = []
    obsidian_path: str | None = None
    for att in attachments:
        att_type = _infer_attachment_type(att)
        if _is_reading_attachment(att):
            result = await _handle_uploaded_document_save(session, att, label)
        elif att_type == "image":
            result = await _handle_uploaded_image_save(session, att, label)
        else:
            result = await _handle_generic_file_save(session, att, label)
        if result.get("reply"):
            replies.append(result["reply"])
        if result.get("obsidian_path") and not obsidian_path:
            obsidian_path = result["obsidian_path"]
    if not replies:
        return {"reply": "Ross: nothing was saved from those attachments."}
    return {"reply": "\n".join(replies), "obsidian_path": obsidian_path}


async def handle_save(
    msg: str,
    session: Session,
    attachments: list[dict] | None = None,
    *,
    history: list[dict] | None = None,
) -> dict:
    # Strip save phrase so it doesn't pollute the extracted content
    cleaned = SAVE_RE.sub("", msg).strip().lstrip(":").strip()
    cleaned = CONTEXTUAL_SAVE_RE.sub("", cleaned).strip()
    urls = _extract_urls(cleaned) or _extract_urls(msg)
    if not urls and history:
        hist_url = _url_from_chat_history(history)
        if hist_url:
            urls = [hist_url]
    attachments = attachments or []
    prefer_pdf = _wants_pdf_download(msg)
    if attachments:
        return await _handle_attachments_save(session, attachments, cleaned)

    if not cleaned and not urls:
        return {
            "reply": (
                "Ross: paste a link or tell me what to save — e.g. "
                "**save this https://openai.com/blog/…** or just paste the URL."
            )
        }

    if len(urls) > 1:
        saved_titles: list[str] = []
        for url in urls[:5]:
            partial = await handle_save(f"save in notes {url}", session, attachments=[])
            if partial.get("reply"):
                m = re.search(r"'([^']+)'", partial["reply"])
                if m:
                    saved_titles.append(m.group(1))
        if saved_titles:
            return {"reply": "🪄 Saved: " + ", ".join(saved_titles)}
        return {"reply": "I couldn't save those URLs right now."}

    title = cleaned
    summary: str | None = None
    source: str | None = None
    tags: str = ""
    kind = ItemKind.URL
    note_body: str | None = None
    url: str | None = None

    if urls:
        url = urls[0]
        source = _domain(url)
        kind = ItemKind.PAPER if "arxiv.org" in url else ItemKind.URL
        fetched_text = ""
        try:
            fetched_text = await fetch_url_text(url)
            if _looks_like_failed_fetch(url, fetched_text):
                title = url
                summary = "Page could not be fetched — open the link directly."
            else:
                parsed = await _extract_article_fields(url, fetched_text)
                title = str(parsed.get("title") or url).strip() or url
                summary = str(parsed.get("summary") or "").strip() or None
                raw_tags = parsed.get("tags") if isinstance(parsed.get("tags"), list) else []
                tags = ",".join(str(t) for t in raw_tags[:4])
        except Exception as e:
            logger.warning("URL extraction failed for {}: {}", url, e)
            title = url
    else:
        url = None
        kind = ItemKind.NOTE
        source = "note"
        note_body = cleaned
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

    if item is None and urls:
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

    if item is None:
        return {"reply": "Could not save that item."}

    content_note = ""
    if note_body:
        item, content_note = await _attach_readable_content(
            session,
            item,
            note_body=note_body,
        )
    elif urls and prefer_pdf:
        item, content_note = await _attach_readable_content(
            session,
            item,
            url=url,
            prefer_pdf=True,
        )
    elif urls:
        content_note = " Tap **Open in Safari** from your Reading list when you're ready."

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
        "reply": f"🪄 Saved '{title}'.{content_note}",
        "obsidian_path": mirror_path,
    }


async def handle_list(msg: str, session: Session) -> dict:
    if LIST_READ_WEEK_RE.search(msg):
        since = datetime.now() - timedelta(days=7)
        done = rl.list_finished_since(session, since)
        if not done:
            return {"reply": "You haven't marked anything read this week yet."}
        lines = [f"- **{i.title}** — finished {_format_date(i.finished_at)}" for i in done[:15]]
        return {"reply": "This week you finished:\n\n" + "\n".join(lines)}

    items = rl.list_active(session)
    filt = LIST_FILTERED_RE.search(msg)
    if filt:
        tag = filt.group(2).strip()
        items = rl.list_by_tag(session, tag, only_active=True)
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

    limit = 100 if "list everything" in msg.lower() else 15
    lines = []
    for item in items[:limit]:
        prog = f" · {item.progress}%" if item.progress else ""
        lines.append(f"- **{item.title}** ({item.source or 'note'} · {item.status}{prog})")
    extra = ""
    if len(items) > limit:
        extra = f"\n\n… and {len(items) - limit} more. Ask 'list everything' to see all."
    return {"reply": header + "\n".join(lines) + extra}


async def handle_mark_read(target: str, session: Session) -> dict:
    matches = rl.search_by_title(
        session,
        target,
        statuses=(ItemStatus.UNREAD, ItemStatus.IN_PROGRESS),
        limit=5,
    )
    if not matches:
        return {
            "reply": (
                f"Couldn't find anything matching '{target}' in your list. "
                "Try 'show my reading list' to see what's there."
            )
        }
    if len(matches) > 1:
        options = [
            f"{idx + 1}) {i.title} ({i.source or 'note'})"
            for idx, i in enumerate(matches)
        ]
        return {"reply": "Which one?\n" + "\n".join(options)}
    item = matches[0]

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

    return {"reply": f"Got it — '{item.title}' at {max(0, min(100, pct))}%."}


async def handle_delete(target: str, session: Session) -> dict:
    item = rl.find_by_title(session, target)
    if not item:
        return {"reply": f"Couldn't find anything matching '{target}' in your list."}

    pending_actions.set_pending(
        "delete_reading_item",
        {"item_id": item.id, "title": item.title},
        ttl_minutes=10,
    )
    return {"reply": f"Delete '{item.title}' from your list? (yes/no)"}


async def handle_delete_confirm(session: Session, confirm: bool) -> dict:
    pending = pending_actions.consume_pending()
    if not pending or pending.kind != "delete_reading_item":
        return {"reply": "There is no pending delete action."}
    if not confirm:
        return {"reply": "Delete cancelled."}

    item = rl.find_by_id(session, int(pending.payload["item_id"]))
    if not item:
        return {"reply": "That item is already gone."}

    mirror = item.mirror_path
    rl.delete(session, item)

    if mirror:
        try:
            async with ObsidianClient() as obsidian:
                await _delete_mirror(mirror, obsidian)
        except Exception as e:
            logger.warning("Mirror delete failed: {}", e)

    return {"reply": f"🗑️ Deleted '{item.title}'."}


async def handle_clear_list(session: Session) -> dict:
    pending_actions.set_pending("clear_reading_list", {}, ttl_minutes=10)
    return {
        "reply": (
            "This will wipe your entire reading list. "
            "Type `confirm clear all` to continue."
        )
    }


async def handle_confirm_clear_list(session: Session) -> dict:
    pending = pending_actions.consume_pending()
    if not pending or pending.kind != "clear_reading_list":
        return {"reply": "No clear-all action is pending."}
    items = rl.list_all(session)
    deleted = 0
    for item in items:
        rl.delete(session, item)
        deleted += 1
    return {"reply": f"Cleared {deleted} reading-list items."}


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


def _top_tags_from_reading_list(session: Session, days: int = 7, limit: int = 5) -> list[str]:
    since = datetime.now() - timedelta(days=days)
    items = [i for i in rl.list_all(session) if i.saved_at >= since]
    counts: dict[str, int] = {}
    for item in items:
        for raw in (item.tags or "").split(","):
            tag = raw.strip().lower()
            if tag:
                counts[tag] = counts.get(tag, 0) + 1
    ranked = sorted(counts, key=counts.get, reverse=True)  # type: ignore[arg-type]
    return ranked[:limit]


def _build_tavily_query(
    profile: GitHubProfile | None,
    interests: list[str],
    *,
    topic_tags: list[str] | None = None,
    recent_tags: list[str] | None = None,
) -> str:
    """Trending query — blends interests, optional topic filter, and recent saves."""
    if topic_tags:
        topic = topic_tags[0]
        recent_part = " OR ".join(recent_tags[:3]) if recent_tags else ""
        base = f"{topic} news 2026 OR {topic} research"
        if recent_part:
            return f"({base}) OR ({recent_part})"
        return base

    if recent_tags:
        return " OR ".join(f"{t} 2026" for t in recent_tags[:4])

    return _build_web_query(profile, interests)


async def _fetch_digest_candidates(
    *,
    interests: list[str],
    topic_tags: list[str] | None = None,
    recent_tags: list[str] | None = None,
    include_web: bool = True,
) -> list[KnowledgeItem]:
    settings = get_settings()
    feed_sources = resolve_feed_sources(interests, topic_tags=topic_tags)
    profile = await _get_github_profile()
    arxiv_interests = topic_tags or interests
    arxiv_query = _build_arxiv_query(profile, arxiv_interests)

    rss_items = await fetch_rss_sources(feed_sources, max_per_feed=3)
    rss_balanced = balance_items_by_tag(rss_items, max_per_tag=4, max_total=24)

    tasks = [search_arxiv(arxiv_query, max_results=10)]
    if include_web:
        web_query = _build_tavily_query(
            profile,
            interests,
            topic_tags=topic_tags,
            recent_tags=recent_tags,
        )
        if settings.tavily_api_key:
            tasks.append(search_tavily(web_query, max_results=8))
        else:
            tasks.append(search_openai_web(web_query, max_results=8))

    extra_lists = await asyncio.gather(*tasks)
    arxiv_items = extra_lists[0]
    web_items = extra_lists[1] if len(extra_lists) > 1 else []
    merged = _dedupe([*rss_balanced, *arxiv_items, *web_items])
    return _prefer_fresh(merged)


async def _fetch_topic_sources(topic: str) -> list[KnowledgeItem]:
    """Fresh web + arXiv results for a specific user topic (not generic interests)."""
    settings = get_settings()
    topic = topic.strip()
    if len(topic.split()) <= 5:
        arxiv_query = topic
    else:
        arxiv_query = f'all:{topic.replace(" ", "+")}'
    web_query = (
        f"{topic} latest news OR recent updates OR official guidance OR amendments 2025 2026"
    )
    tasks: list = [search_arxiv(arxiv_query, max_results=8)]
    if settings.tavily_api_key:
        tasks.append(search_tavily_with_options(web_query, max_results=8, topic="general"))
    else:
        tasks.append(search_openai_web(web_query, max_results=8))
    arxiv_items, web_items = await asyncio.gather(*tasks)
    return _prefer_fresh(_dedupe([*arxiv_items, *web_items]))


async def handle_digest_now(msg: str = "", history: list[dict] | None = None) -> dict:
    settings = get_settings()
    topic_tags = extract_topic_tags_from_message(msg) if msg else None
    search_topic = _extract_search_topic(msg, history)

    with next(get_session()) as session:
        recent_tags = _top_tags_from_reading_list(session)

    topic = search_topic or (topic_tags[0] if topic_tags else None)
    if topic:
        merged = await _fetch_topic_sources(topic)
    else:
        merged = await _fetch_digest_candidates(
            interests=settings.interest_list,
            topic_tags=topic_tags,
            recent_tags=recent_tags,
        )
    merged = _rank_by_topic_relevance(merged, topic)[:MAX_SUGGEST_ITEMS]
    if not merged:
        return {"reply": "🪄 Ross couldn't find fresh items right now. Try again in a bit."}

    profile = await _get_github_profile()
    structured = [
        {
            "title": item.title,
            "url": item.url,
            "summary": item.summary,
            "source": item.source or "",
            "date": _format_date(item.published),
            "kind": "paper" if "arxiv.org" in (item.url or "") else "url",
            "tag": item.genre or "",
        }
        for item in merged
    ]

    scope = f" on **{topic}**" if topic else (f" in {topic_tags[0]}" if topic_tags else "")
    context_note = ""
    if profile and not topic:
        context_note = f" (personalised for your {', '.join(profile.languages[:2])} projects)"

    preview_lines = [
        f"- **{item.title}** — {_short(item.summary, 120)} "
        f"(*{item.source} · {_format_date(item.published)}"
        f"{f' · {item.genre}' if item.genre else ''}*)"
        for item in merged
    ]
    suggest_items = _collect_suggest_items(
        merged,
        existing_urls=set(),
        topic=topic,
        limit=MAX_SUGGEST_ITEMS,
    )

    reply = (
        f"🪄 Ross found {len(merged)} fresh items{scope}{context_note}:\n\n"
        + "\n".join(preview_lines)
        + "\n\n_Select any below to preview and add to your reading list._"
    )
    return {
        "reply": reply,
        "digest_items": structured,
        "suggest_items": suggest_items,
    }


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


def _extract_query_topic(msg: str) -> str:
    ok, topic = is_query_command(msg)
    if ok:
        return topic
    return msg.strip()


def _search_obsidian_mentions(topic: str, limit: int = 5) -> list[dict[str, str]]:
    settings = get_settings()
    if not settings.obsidian_vault_path:
        return []
    root = Path(settings.obsidian_vault_path)
    if not root.exists():
        return []
    topic_l = topic.lower()
    scopes = [
        root / "01-Knowledge",
        root / "00-Inbox" / "Daily",
        root / "04-People",
    ]
    hits: list[dict[str, str]] = []
    for scope in scopes:
        if not scope.exists():
            continue
        for file in scope.rglob("*.md"):
            try:
                text = file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if topic_l not in text.lower():
                continue
            idx = text.lower().find(topic_l)
            snippet = text[max(0, idx - 80): idx + min(len(topic), 40) + 80].replace("\n", " ")
            rel = file.relative_to(root).as_posix()
            hits.append({"path": rel, "snippet": _short(snippet, 140)})
            if len(hits) >= limit:
                return hits
    return hits


async def handle_query(msg: str, session: Session) -> dict:
    topic = _extract_query_topic(msg)
    if not topic:
        return {"reply": "What topic should I look up?"}

    db_hits = rl.search_by_title(session, topic, limit=5)
    file_hits = _search_obsidian_mentions(topic, limit=5)

    if not db_hits and not file_hits:
        return {
            "reply": (
                f"I don't have anything saved about '{topic}'. "
                "Want me to find recent papers on it?"
            )
        }

    total_hits = len(db_hits) + len(file_hits)
    lines: list[str] = [f"You've encountered '{topic}' in {total_hits} places:\n"]
    for i in db_hits[:5]:
        lines.append(
            f"- **{i.title}** — saved {_format_date(i.saved_at)}, {i.progress}% read. "
            f"{i.mirror_path or 'reading_list_items'}"
        )
    for f in file_hits[:5]:
        lines.append(f"- {f['path']}: \"{f['snippet']}\"")
    more = (len(db_hits) + len(file_hits)) - 5
    if more > 0:
        lines.append(f"- … and {more} more matches. Try a more specific term.")
    return {"reply": "\n".join(lines)}


def _estimate_minutes(item: ReadingListItem) -> int:
    text = (item.summary or item.title or "").strip()
    return _estimate_minutes_from_text(text)


def _estimate_minutes_from_text(text: str) -> int:
    words = max(80, len(text.split()))
    return max(3, round(words / 200))


def _pdf_preview_url(url: str) -> str | None:
    from src.services.reading_content import is_probable_pdf_url, resolve_pdf_url

    if not url:
        return None
    if is_probable_pdf_url(url):
        return resolve_pdf_url(url)
    return None


def _feed_item_to_suggest(
    item: KnowledgeItem,
    *,
    existing_urls: set[str],
) -> dict | None:
    url = (item.url or "").strip()
    if not url or url in existing_urls:
        return None
    summary = (item.summary or "").strip() or "Fresh pick from the web."
    payload: dict = {
        "id": f"feed-{abs(hash(url))}",
        "title": item.title,
        "url": url,
        "summary": _short(summary, 280),
        "source": item.source or "web",
        "date": _format_date(item.published),
        "kind": "paper" if "arxiv.org" in url else "url",
        "tag": item.genre or "",
        "est_minutes": _estimate_minutes_from_text(summary),
        "in_list": False,
        "list_item_id": None,
    }
    preview = _pdf_preview_url(url)
    if preview:
        payload["pdf_preview_url"] = preview
    return payload


def _topic_search_terms(topic: str) -> list[str]:
    terms = [t for t in re.findall(r"[a-z0-9']+", topic.lower()) if len(t) >= 3]
    return terms or [topic.lower().strip()]


def _topic_relevance_score(item: KnowledgeItem, terms: list[str]) -> int:
    title = item.title.lower()
    body = (item.summary or "").lower()
    score = 0
    for term in terms:
        if term in title:
            score += 10
        if term in body:
            score += 3
    return score


def _rank_by_topic_relevance(
    items: list[KnowledgeItem],
    topic: str | None,
) -> list[KnowledgeItem]:
    if not topic:
        return _prefer_fresh(items)
    terms = _topic_search_terms(topic)

    def _key(item: KnowledgeItem) -> tuple[int, datetime]:
        pub = item.published or datetime.min
        if pub.tzinfo is not None:
            pub = pub.replace(tzinfo=None)
        return (_topic_relevance_score(item, terms), pub)

    return sorted(items, key=_key, reverse=True)


def _collect_suggest_items(
    feed_items: list[KnowledgeItem],
    *,
    existing_urls: set[str],
    topic: str | None = None,
    limit: int = MAX_SUGGEST_ITEMS,
) -> list[dict]:
    """Return up to `limit` selectable suggestions, ranked by topic relevance."""
    ranked = _rank_by_topic_relevance(feed_items, topic)
    suggestions: list[dict] = []
    seen_urls: set[str] = set()
    for item in ranked:
        row = _feed_item_to_suggest(item, existing_urls=existing_urls | seen_urls)
        if not row:
            continue
        suggestions.append(row)
        seen_urls.add(row["url"])
        if len(suggestions) >= limit:
            break
    return suggestions


def _extract_research_topic(msg: str) -> str:
    for pat in (
        r"(?:papers?|articles?|research)\s+(?:on|about|for|regarding)\s+(.+?)[?.!]*$",
        r"find\s+(?:me\s+)?(?:\d+\s+)?(?:papers?|articles?)\s+(?:on|about|for)?\s*(.+?)[?.!]*$",
        r"(?:search|look up)\s+(?:for\s+)?(?:papers?|articles?)\s+(?:on|about)?\s*(.+?)[?.!]*$",
        r"(?:what'?s new|latest|recent)\s+(?:in|on|about)\s+(.+?)[?.!]*$",
    ):
        m = re.search(pat, msg, re.IGNORECASE)
        if m:
            topic = m.group(1).strip(" .,-?!")
            if topic and len(topic) >= 2:
                return topic
    tags = extract_topic_tags_from_message(msg)
    if tags:
        return tags[0]
    cleaned = RESEARCH_RE.sub("", msg)
    cleaned = re.sub(
        r"\b(find|search|me|please|can you|could you|papers?|articles?)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,-?!")
    return cleaned if len(cleaned) >= 2 else msg.strip()


_TOPIC_JUNK = frozenset(
    {
        "you",
        "these",
        "this",
        "that",
        "what i asked",
        "what i asked you",
        "my question",
        "related to what i asked",
    }
)


def _topic_from_history_only(history: list[dict] | None) -> str | None:
    if not history:
        return None
    for turn in reversed(history):
        if turn.get("role") != "user":
            continue
        prior = _extract_search_topic(turn.get("content", ""), None)
        if prior:
            return prior
    return None


def _extract_search_topic(msg: str, history: list[dict] | None = None) -> str | None:
    """Pull a concrete search topic from the message or recent user turns."""
    lowered = msg.strip().lower()
    if is_suggest_command(lowered)[0] or is_digest_command(msg):
        return _topic_from_history_only(history)

    if re.search(r"\b(not related|unrelated|wrong|off topic|same three)\b", msg, re.I):
        return _topic_from_history_only(history)

    for pat in (
        r"(?:what (?:are|is)|tell me about)\s+(?:the\s+)?(?:latest\s+)?(?:amendments?\s+(?:to|of)\s+)?(.+?)[?.!]*$",
        r"(?:latest|recent)\s+(?:news|updates?|developments?|amendments?)\s+(?:to|on|about|in)\s+(?:the\s+)?(.+?)[?.!]*$",
        r"(?:find|search|look up)\s+(?:for\s+)?(?:info(?:rmation)?|articles?|news|sources?)\s+(?:on|about)\s+(.+?)[?.!]*$",
        r"(?:show me|pull up)\s+(?:info(?:rmation)?|articles?|news|sources?)\s+(?:on|about)\s+(.+?)[?.!]*$",
    ):
        m = re.search(pat, msg, re.IGNORECASE)
        if m:
            topic = m.group(1).strip(" .,-?!")
            if topic and len(topic) >= 2 and topic.lower() not in _TOPIC_JUNK:
                return topic

    topic = _extract_research_topic(msg)
    if topic and len(topic) >= 2:
        low = topic.lower()
        if low not in _TOPIC_JUNK and not low.startswith("what i"):
            if not is_suggest_command(low)[0] and not is_digest_command(msg):
                return topic

    return _topic_from_history_only(history)


def is_topic_search_command(msg: str, history: list[dict] | None = None) -> bool:
    lowered = msg.strip().lower()
    if is_research_command(msg) or is_suggest_command(lowered)[0] or is_digest_command(lowered):
        return False
    topic = _extract_search_topic(msg, history)
    if not topic:
        return False
    search_cues = (
        "latest",
        "recent",
        "new",
        "news",
        "update",
        "amendment",
        "what are",
        "what is",
        "what's",
        "whats",
        "tell me",
        "find",
        "search",
        "look up",
        "show me",
        "pull up",
        "not related",
        "unrelated",
        "wrong",
        "off topic",
        "same three",
    )
    if any(cue in lowered for cue in search_cues):
        return True
    return "?" in msg and len(topic.split()) >= 1


async def handle_topic_search(msg: str, session: Session, history: list[dict] | None = None) -> dict:
    topic = _extract_search_topic(msg, history)
    if not topic:
        return await handle_chat(msg, history or [])

    existing_urls = {i.url for i in rl.list_all(session) if i.url}
    merged = await _fetch_topic_sources(topic)
    suggestions = _collect_suggest_items(
        merged,
        existing_urls=existing_urls,
        topic=topic,
        limit=MAX_SUGGEST_ITEMS,
    )
    if not suggestions:
        return {
            "reply": (
                f"I searched for fresh sources on **{topic}** but didn't get good hits. "
                "Try rephrasing — e.g. **find papers on STCW amendments** — or check your Tavily key."
            )
        }

    preview_lines = [
        f"{idx}. **{s['title']}** — {_short(s['summary'], 90)} (~{s['est_minutes']} min)"
        for idx, s in enumerate(suggestions, 1)
    ]
    reply = (
        f"📄 **Top reads on {topic}**\n\n"
        + "\n".join(preview_lines)
        + "\n\n_Select any below to preview and add to your reading list._"
    )
    return {"reply": reply, "suggest_items": suggestions}


async def _build_reading_suggestions(
    session: Session,
    *,
    max_minutes: int | None = None,
    topic_tags: list[str] | None = None,
    search_topic: str | None = None,
    count: int = 3,
) -> list[dict]:
    """Blend fresh feed picks with saved list items — fresh internet content first."""
    settings = get_settings()
    existing_urls = {
        i.url for i in rl.list_all(session) if i.url
    }

    unread = [i for i in rl.list_active(session) if i.status != ItemStatus.READ]
    if max_minutes is not None:
        unread = [i for i in unread if _estimate_minutes(i) <= max_minutes]

    scored = sorted(
        unread,
        key=lambda i: (
            0 if i.status == ItemStatus.IN_PROGRESS else 1,
            -(i.progress if i.status == ItemStatus.IN_PROGRESS else 0),
            -(i.saved_at.timestamp()),
        ),
    )

    suggestions: list[dict] = []
    seen_urls: set[str] = set()

    recent_tags = _top_tags_from_reading_list(session)
    topic = search_topic or (topic_tags[0] if topic_tags else None)
    if topic and not topic_tags:
        merged = await _fetch_topic_sources(topic)
    else:
        merged = await _fetch_digest_candidates(
            interests=settings.interest_list,
            topic_tags=topic_tags,
            recent_tags=recent_tags,
        )

    def _append_feed_item(feed_item: KnowledgeItem) -> bool:
        row = _feed_item_to_suggest(
            feed_item,
            existing_urls=existing_urls | seen_urls,
        )
        if not row:
            return False
        if max_minutes is not None and row["est_minutes"] > max_minutes:
            return False
        suggestions.append(row)
        seen_urls.add(row["url"])
        return True

    for feed_item in merged:
        if len(suggestions) >= count:
            break
        _append_feed_item(feed_item)

    if len(suggestions) < count:
        for item in scored:
            if len(suggestions) >= count:
                break
            if item.url and item.url in seen_urls:
                continue
            sid = f"list-{item.id}"
            summary = (item.summary or "").strip() or (
                "Already on your reading list — a good pick to continue today."
            )
            suggestions.append(
                {
                    "id": sid,
                    "title": item.title,
                    "url": item.url,
                    "summary": _short(summary, 280),
                    "source": item.source or str(item.kind),
                    "date": _format_date(item.saved_at),
                    "kind": item.kind.value if hasattr(item.kind, "value") else str(item.kind),
                    "tag": next(
                        (t.strip() for t in (item.tags or "").split(",") if t.strip()),
                        "",
                    ),
                    "est_minutes": _estimate_minutes(item),
                    "in_list": True,
                    "list_item_id": item.id,
                }
            )
            if item.url:
                seen_urls.add(item.url)

    return suggestions[:count]


async def handle_research_search(msg: str, session: Session) -> dict:
    """Find papers and articles via arXiv + Tavily — selectable reading list picks."""
    topic = _extract_research_topic(msg)
    if len(topic) < 2:
        return {
            "reply": (
                "What topic should I search? "
                "Try **find papers on transformers** or **research articles about climate**."
            )
        }

    settings = get_settings()
    arxiv_query = topic if len(topic.split()) <= 5 else f"all:{topic.replace(' ', '+')}"
    tasks: list = [search_arxiv(arxiv_query, max_results=10)]
    web_query = f"{topic} research paper OR scientific article pdf"
    if settings.tavily_api_key:
        tasks.append(search_tavily_with_options(web_query, max_results=8, topic="general"))
    else:
        tasks.append(search_openai_web(web_query, max_results=8))

    arxiv_items, web_items = await asyncio.gather(*tasks)
    merged = _dedupe([*arxiv_items, *web_items])

    existing_urls = {i.url for i in rl.list_all(session) if i.url}
    suggestions = _collect_suggest_items(
        merged,
        existing_urls=existing_urls,
        topic=topic,
        limit=MAX_SUGGEST_ITEMS,
    )

    if not suggestions:
        return {
            "reply": (
                f"I couldn't find papers or articles on **{topic}** right now. "
                "Try a broader topic or check your Tavily API key in `.env`."
            )
        }

    preview_lines = [
        f"{idx}. **{s['title']}** — {_short(s['summary'], 90)} (~{s['est_minutes']} min)"
        for idx, s in enumerate(suggestions, 1)
    ]
    reply = (
        f"📄 **{len(suggestions)} reads on {topic}**\n\n"
        + "\n".join(preview_lines)
        + "\n\n_Expand a card to preview PDFs when available, then add picks to your reading list._"
    )
    return {"reply": reply, "suggest_items": suggestions}


async def handle_suggest(msg: str, session: Session, history: list[dict] | None = None) -> dict:
    _, max_minutes = is_suggest_command(msg)
    topic_tags = extract_topic_tags_from_message(msg)
    search_topic = _topic_from_history_only(history)

    suggestions = await _build_reading_suggestions(
        session,
        max_minutes=max_minutes,
        topic_tags=topic_tags,
        search_topic=search_topic if not topic_tags else None,
        count=MAX_SUGGEST_ITEMS,
    )

    if not suggestions:
        return {
            "reply": (
                "I couldn't find good picks right now — your list is empty and feeds are quiet. "
                "Try `what's new in AI` for a fresh digest, or `find free books on philosophy`."
            )
        }

    scope = f" on **{topic_tags[0]}**" if topic_tags else ""
    time_note = f" (≤{max_minutes} min)" if max_minutes else ""
    preview_lines = [
        f"{idx}. **{s['title']}** — {_short(s['summary'], 100)} (~{s['est_minutes']} min)"
        for idx, s in enumerate(suggestions, 1)
    ]
    reply = (
        f"📖 **{len(suggestions)} reads for today{scope}{time_note}**\n\n"
        + "\n".join(preview_lines)
        + "\n\n_Select any below to preview and add to your reading list._"
    )
    return {"reply": reply, "suggest_items": suggestions}


def _format_book_search_results(
    gutenberg: list[BookResult],
    open_library: list,
    audiobooks: list,
) -> str:
    lines: list[str] = []

    if gutenberg:
        lines.append("**Project Gutenberg (free download):**\n")
        for idx, book in enumerate(gutenberg[:5], 1):
            subjects = ", ".join(book.subject_tags[:3]) or "general"
            dl = "✓ downloadable" if book_has_download(book) else "metadata only"
            lines.append(
                f"{idx}. **{book.title}** — {book.author_line}\n"
                f"   _{subjects}_ · {dl}"
            )

    if open_library:
        lines.append("\n**Open Library (discovery / borrow):**\n")
        for book in open_library[:3]:
            borrow = " · borrowable scan" if book.public_scan or book.has_fulltext else ""
            lines.append(
                f"- **{book.title}** — {book.author_line}{borrow}\n"
                f"  [{book.title}]({book.url})"
            )

    if audiobooks:
        lines.append("\n**LibriVox (free audiobooks):**\n")
        for book in audiobooks[:3]:
            dur = f" · {book.duration_label}" if book.duration_label else ""
            link = book.url or "https://librivox.org"
            lines.append(
                f"- **{book.title}** — {book.author_line}{dur}\n"
                f"  [{book.title}]({link})"
            )

    if not lines:
        return (
            "I couldn't find matching free books. Try a different title, author, or topic."
            + _book_not_found_extras("your search")
        )
    lines.append("\n_Use the cards below to download, or say `download <exact title>`._")
    return "\n".join(lines)


def _gutenberg_to_book_item(book: BookResult) -> dict:
    subjects = ", ".join(book.subject_tags[:3]) or "classic"
    return {
        "id": f"gutenberg-{book.id}",
        "gutenberg_id": book.id,
        "title": book.title,
        "authors": book.author_line,
        "summary": f"Public-domain · {book.author_line}. Topics: {subjects}.",
        "url": book.canonical_url,
        "source": "gutenberg",
        "kind": "ebook",
        "downloadable": book_has_download(book),
        "in_list": False,
    }


def _build_book_items(
    gutenberg: list[BookResult],
    open_library: list,
    audiobooks: list,
) -> list[dict]:
    items: list[dict] = []
    for book in gutenberg[:6]:
        items.append(_gutenberg_to_book_item(book))
    for book in open_library[:3]:
        items.append(
            {
                "id": f"openlibrary-{book.key}",
                "gutenberg_id": None,
                "title": book.title,
                "authors": book.author_line,
                "summary": (
                    "Open Library — borrow or read online if your library participates. "
                    "Not auto-downloaded."
                ),
                "url": book.url,
                "source": "openlibrary",
                "kind": "ebook",
                "downloadable": False,
                "in_list": False,
            }
        )
    for book in audiobooks[:3]:
        link = book.url or "https://librivox.org"
        items.append(
            {
                "id": f"librivox-{book.id}",
                "gutenberg_id": None,
                "title": book.title,
                "authors": book.author_line,
                "summary": f"Free audiobook · {book.duration_label or 'LibriVox'}.",
                "url": link,
                "source": "librivox",
                "kind": "audiobook",
                "downloadable": False,
                "in_list": False,
            }
        )
    return items


def _include_unofficial_book_links() -> bool:
    return get_settings().book_unofficial_links


def _is_strong_gutenberg_match(book: BookResult, query: str) -> bool:
    """Only auto-download when the title clearly matches the user's query."""
    q = query.lower().strip()
    title_l = book.title.lower()
    if q in title_l:
        return True
    if any(q in author.lower() for author in book.authors):
        return True
    q_words = {w for w in re.findall(r"[a-z0-9']+", q) if len(w) > 2}
    if not q_words:
        return False
    title_words = set(re.findall(r"[a-z0-9']+", title_l))
    overlap = len(q_words & title_words) / len(q_words)
    return overlap >= 0.6


async def _oceanofpdf_link(query: str) -> OceanOfPdfMatch | None:
    if not _include_unofficial_book_links():
        return None
    try:
        return await asyncio.wait_for(resolve_oceanofpdf(query), timeout=8.0)
    except TimeoutError:
        logger.info("Ocean of PDF resolve timed out for {!r}, using search URL", query)
        return oceanofpdf_search_match(query)
    except Exception as exc:
        logger.warning("Ocean of PDF resolve failed for {!r}: {}", query, exc)
        return oceanofpdf_search_match(query)


def _build_web_pdf_book_items(links: list[KnowledgeItem]) -> list[dict]:
    items: list[dict] = []
    for link in links:
        url = (link.url or "").strip()
        if not url:
            continue
        items.append(
            {
                "id": f"webpdf-{abs(hash(url))}",
                "gutenberg_id": None,
                "title": link.title or "PDF download link",
                "authors": link.source or "Web search",
                "summary": _short(
                    link.summary or "Possible PDF — tap Open in Safari to check this link.",
                    220,
                ),
                "url": url,
                "source": "web",
                "kind": "ebook",
                "downloadable": False,
                "in_list": False,
            }
        )
    return items


def _append_oceanofpdf_item(
    items: list[dict],
    query: str,
    match: OceanOfPdfMatch | None,
) -> list[dict]:
    """Add Ocean of PDF card only when unofficial links are enabled."""
    if not _include_unofficial_book_links() or not match:
        return items
    card = build_oceanofpdf_book_item(query, match)
    if any(i.get("url") == card["url"] for i in items):
        return items
    return [*items, card]


def _book_not_found_extras(
    query: str,
    oceanofpdf_match: OceanOfPdfMatch | None = None,
    *,
    include_ocean: bool = True,
) -> str:
    return format_book_not_found_alternatives(
        query,
        oceanofpdf_match=oceanofpdf_match,
        include_ocean=include_ocean,
    )


async def _build_download_fallback_response(
    query: str,
    *,
    gutenberg: list[BookResult],
    open_library: list,
    audiobooks: list,
    intro: str,
) -> dict:
    """Picker + legal links; web PDF search via Tavily, then Ocean of PDF as fallback."""
    book_items = _build_book_items(gutenberg, open_library, audiobooks)

    web_links = await search_web_book_pdf_links(query)
    if web_links:
        book_items = [*book_items, *_build_web_pdf_book_items(web_links)]

    oopdf = await _oceanofpdf_link(query) if _include_unofficial_book_links() else None
    book_items = _append_oceanofpdf_item(book_items, query, oopdf)

    web_note = (
        f"\n\n**Web search:** found {len(web_links)} possible PDF link(s) — try those first."
        if web_links
        else ""
    )
    oopdf_md = ""
    if oopdf:
        label = f"Search «{query}» on Ocean of PDF" if oopdf.is_search else oopdf.title
        oopdf_md = f"\n\n**Ocean of PDF (fallback):** [{label}]({oopdf.url})"

    reply = intro + web_note + oopdf_md + _book_not_found_extras(
        query,
        oopdf,
        include_ocean=bool(oopdf),
    )
    return {"reply": reply, "book_items": book_items}


async def _save_gutenberg_book(session: Session, book: BookResult) -> dict:
    if not book_has_download(book):
        return {
            "reply": (
                f"**{book.title}** is on Gutenberg but has no plain-text/PDF format I can save. "
                f"Try another edition, or open [the catalog page]({book.canonical_url})."
            ),
            "book_items": [_gutenberg_to_book_item(book)],
        }

    title = book.title
    summary = f"Public-domain ebook by {book.author_line}."
    tags = ",".join(book.subject_tags) if book.subject_tags else "ebook,classic"

    item = rl.add(
        session,
        url=book.canonical_url,
        title=title,
        summary=summary,
        source="gutenberg",
        kind=ItemKind.EBOOK,
        tags=tags,
    )
    if item is None:
        existing = rl.find_by_title(session, title)
        if existing:
            return {
                "reply": (
                    f"You already have **{existing.title}** in your list. "
                    "Tap **Read** in your Reading list to continue."
                )
            }
        return {"reply": f"You already saved '{title}'."}

    content_path, fmt = await rc.save_gutenberg_book(
        item.id,
        title=title,
        author_line=book.author_line,
        formats=book.formats,
        canonical_url=book.canonical_url,
    )
    if content_path:
        item.content_path = content_path
        if fmt == "pdf":
            item.kind = ItemKind.PDF
        session.add(item)
        session.commit()
        session.refresh(item)

    mirror_path = None
    try:
        async with ObsidianClient() as obsidian:
            mirror_path = await _write_mirror(item, obsidian)
        item.mirror_path = mirror_path
        session.add(item)
        session.commit()
    except Exception as exc:
        logger.warning("Mirror write failed for book {}: {}", title, exc)

    read_note = " Tap **Read** in your Reading list." if content_path else ""
    fmt_label = {"text": "full text", "pdf": "PDF", "epub": "EPUB"}.get(fmt, "file")
    if not content_path:
        read_note = (
            " Download didn't finish — try again or pick another edition below."
        )
    return {
        "reply": (
            f"📚 Downloaded **{title}** from Project Gutenberg ({fmt_label}).{read_note}\n"
            f"Tags: {tags.replace(',', ', ')}"
        ),
        "obsidian_path": mirror_path,
    }


async def handle_find_book(
    msg: str,
    session: Session,
    *,
    history: list[dict] | None = None,
) -> dict:
    query = _resolve_book_query(msg, history)
    if len(query) < 2:
        return {"reply": "What topic or book should I search for? e.g. `free books on stoicism`"}

    gutenberg, open_library, audiobooks = await asyncio.gather(
        search_gutenberg_broad(query, limit=6),
        search_open_library(query, limit=4),
        search_librivox(query, limit=4),
    )
    book_items = _build_book_items(gutenberg, open_library, audiobooks)
    reply = _format_book_search_results(gutenberg, open_library, audiobooks)
    if book_items:
        reply += (
            "\n\n**Pick a book below** — Gutenberg titles download in-app; "
            "others open in Safari."
        )
    downloadable = [b for b in gutenberg if book_has_download(b)]
    if not downloadable:
        reply += _book_not_found_extras(query, include_ocean=False)
    return {"reply": reply, "book_items": book_items}


async def handle_download_book(
    msg: str,
    session: Session,
    *,
    history: list[dict] | None = None,
) -> dict:
    query = _resolve_book_query(msg, history)
    if _is_vague_book_query(query) or len(query) < 2:
        return {
            "reply": (
                "Oh! Yes — which book should I grab for you? "
                "Try **download Verity** or **help me read Verity** — "
                "I'll search Gutenberg first, then the web for PDF links."
            )
        }

    gutenberg = await search_gutenberg_broad(query, limit=8)
    downloadable = [b for b in gutenberg if book_has_download(b)]
    strong = [b for b in downloadable if _is_strong_gutenberg_match(b, query)]

    if len(strong) > 1:
        oopdf = await _oceanofpdf_link(query)
        items = _append_oceanofpdf_item(_build_book_items(strong, [], []), query, oopdf)
        reply = f"Found several matches for **{query}** — pick one to download:"
        if oopdf:
            label = f"Search for «{query}»" if oopdf.is_search else oopdf.title
            reply += f"\n\n**Ocean of PDF:** [{label}]({oopdf.url})"
        return {"reply": reply, "book_items": items}

    if len(strong) == 1:
        return await _save_gutenberg_book(session, strong[0])

    open_library, audiobooks = await asyncio.gather(
        search_open_library(query, limit=4),
        search_librivox(query, limit=3),
    )
    return await _build_download_fallback_response(
        query,
        gutenberg=gutenberg,
        open_library=open_library,
        audiobooks=audiobooks,
        intro=(
            f"Okay so — no Gutenberg hit for **{query}** (it's probably still in copyright). "
            "I searched the web for PDF links and listed legal options below — "
            "tap **Open in Safari** on a link, or say **download <title>** again."
        ),
    )


async def handle_download_gutenberg_id(session: Session, book_id: int) -> dict:
    book = await get_gutenberg_book(book_id)
    if not book:
        return {"reply": f"Could not find Gutenberg book #{book_id}."}
    return await _save_gutenberg_book(session, book)


async def handle_download_audiobook(msg: str, session: Session) -> dict:
    query = _extract_book_query(msg)
    results = await search_librivox(query, limit=5)
    if not results:
        return {"reply": f"No LibriVox audiobook found for **{query}**."}
    book = results[0]
    tags = "audiobook,librivox"
    item = rl.add(
        session,
        url=book.url or f"https://librivox.org/book/{book.id}",
        title=book.title,
        summary=f"Free audiobook narrated from public-domain text. {book.author_line}.",
        source="librivox",
        kind=ItemKind.AUDIOBOOK,
        tags=tags,
    )
    if item is None:
        return {"reply": f"You already saved '{book.title}'."}

    body = (
        f"# {book.title}\n\n"
        f"*{book.author_line} · LibriVox*\n\n"
        f"Listen at: {book.url}\n\n"
        f"Duration: {book.duration_label or 'unknown'} · {book.sections} sections"
    )
    item.content_path = rc.write_markdown(item.id, body)
    session.add(item)
    session.commit()

    mirror_path = None
    try:
        async with ObsidianClient() as obsidian:
            mirror_path = await _write_mirror(item, obsidian)
        item.mirror_path = mirror_path
        session.add(item)
        session.commit()
    except Exception as exc:
        logger.warning("Audiobook mirror failed: {}", exc)

    return {
        "reply": (
            f"🎧 Saved audiobook **{book.title}** ({book.duration_label or 'LibriVox'}). "
            f"Open the link in **Read** or listen at {book.url}"
        ),
        "obsidian_path": mirror_path,
    }


def _parse_vocab_from_message(msg: str) -> tuple[str, str, str | None] | None:
    cleaned = LOG_VOCAB_RE.sub("", msg).strip().lstrip(":").strip()
    for line in cleaned.splitlines():
        line = line.strip()
        if not line:
            continue
        m = VOCAB_LINE_RE.match(line)
        if m:
            return m.group("word").lower(), m.group("def").strip(), None
    if " meaning " in cleaned.lower():
        parts = re.split(r"\bmeaning\b", cleaned, maxsplit=1, flags=re.I)
        if len(parts) == 2:
            word = parts[0].strip(" :,-").split()[-1]
            definition = parts[1].strip(" :,-")
            if word and definition:
                return word.lower(), definition, None
    if cleaned:
        return cleaned.split()[0].lower(), cleaned, None
    return None


async def handle_log_vocab(msg: str, session: Session) -> dict:
    parsed = _parse_vocab_from_message(msg)
    if not parsed:
        return {
            "reply": (
                "Format: `log vocab: ephemeral — lasting a short time` "
                "or `learned word serendipity meaning pleasant surprise`"
            )
        }
    word, definition, context = parsed

    source_title = None
    from_match = re.search(r"\bfrom\s+(.+)$", definition, re.I)
    tags = ""
    if from_match:
        source_title = from_match.group(1).strip().rstrip(".")
        definition = definition[: from_match.start()].strip(" .,-")
        source_item = rl.find_by_title(session, source_title)
        if source_item:
            tags = source_item.tags or ""
            source_title = source_item.title

    entry = vocab_service.add_word(
        session,
        word=word,
        definition=definition,
        context=context,
        source_title=source_title,
        source_item_id=None,
        tags=tags,
    )

    mirror_path = None
    try:
        async with ObsidianClient() as obsidian:
            note = (
                f"---\nword: {entry.word}\n"
                f"source: {entry.source_title or ''}\n"
                f"tags: [{entry.tags}]\n"
                f"logged_at: {entry.logged_at.strftime('%Y-%m-%d')}\n---\n\n"
                f"# {entry.word}\n\n{entry.definition}\n"
            )
            path = f"{VOCAB_DIR}/{entry.word}.md"
            await obsidian.create_note(path, note)
            mirror_path = path
    except Exception as exc:
        logger.warning("Vocab mirror failed: {}", exc)

    return {
        "reply": f"📝 Logged **{entry.word}** — {entry.definition[:120]}",
        "obsidian_path": mirror_path,
    }


async def handle_list_vocab(msg: str, session: Session) -> dict:
    tag_match = re.search(r"\b(?:on|about|tagged)\s+([a-z0-9\- ]+)$", msg, re.I)
    if tag_match:
        entries = vocab_service.list_by_tag(session, tag_match.group(1).strip())
    else:
        entries = vocab_service.list_recent(session, limit=20)

    if not entries:
        return {
            "reply": (
                "No vocabulary logged yet. "
                "Try `log vocab: ephemeral — lasting a short time` while you read."
            )
        }

    lines = ["**Your vocabulary:**\n"]
    for entry in entries[:15]:
        src = f" _({entry.source_title})_" if entry.source_title else ""
        lines.append(f"- **{entry.word}** — {entry.definition[:100]}{src}")
    stats = vocab_service.stats(session)
    lines.append(f"\n_{stats['total_words']} words total · {stats['words_this_week']} this week_")
    return {"reply": "\n".join(lines)}


async def handle_apple_books_from_db(msg: str, session: Session) -> dict:
    """Answer Apple Books reading questions using synced DB data (works on cloud)."""
    from sqlmodel import select

    from src.storage.models import ItemStatus

    books = session.exec(
        select(ReadingListItem).where(ReadingListItem.tags.contains("apple-books"))  # type: ignore[arg-type]
    ).all()

    if not books:
        return {
            "output": (
                "No Apple Books data synced yet. Run the Mac sync script to pull your library:\n\n"
                "```bash\nexport SECOND_BRAIN_API_URL=https://your-app.onrender.com\n"
                "export SECOND_BRAIN_API_TOKEN=your-token\n"
                "python3 scripts/sync_apple_books.py\n```"
            )
        }

    currently_reading = [b for b in books if b.status == ItemStatus.IN_PROGRESS]
    finished          = [b for b in books if b.status == ItemStatus.DONE]
    unread            = [b for b in books if b.status == ItemStatus.UNREAD]

    genres: dict[str, int] = {}
    for book in books:
        for tag in (book.tags or "").split(","):
            tag = tag.strip()
            if tag and tag != "apple-books":
                genres[tag] = genres.get(tag, 0) + 1
    top_genres = sorted(genres.items(), key=lambda x: x[1], reverse=True)[:5]

    lowered = msg.lower()

    # Currently reading
    _reading_now_kws = ["currently reading", "reading now", "in progress", "what am i reading"]
    if any(w in lowered for w in _reading_now_kws):
        if not currently_reading:
            return {"output": "No books currently in progress in your Apple Books library."}
        lines = ["**Currently reading:**\n"]
        for b in currently_reading:
            lines.append(f"- **{b.title}** by {b.source or 'Unknown'} — {b.progress}% complete")
        return {"output": "\n".join(lines)}

    # Finished books
    if any(w in lowered for w in ["finished", "completed", "read books", "have i read"]):
        recently = sorted(finished, key=lambda x: x.finished_at or datetime.min, reverse=True)[:10]
        lines = [f"**Finished books ({len(finished)} total):**\n"]
        for b in recently:
            date_str = f" — finished {b.finished_at.strftime('%b %Y')}" if b.finished_at else ""
            lines.append(f"- **{b.title}** by {b.source or 'Unknown'}{date_str}")
        return {"output": "\n".join(lines)}

    # Reading stats / habits
    lines = [
        "**Your Apple Books reading habits:**\n",
        f"- **Total books:** {len(books)}",
        f"- **Currently reading:** {len(currently_reading)}",
        f"- **Finished:** {len(finished)}",
        f"- **Want to read:** {len(unread)}",
    ]
    if currently_reading:
        lines.append("\n**In progress:**")
        for b in currently_reading[:5]:
            lines.append(f"  - {b.title} ({b.progress}%)")
    if top_genres:
        lines.append("\n**Top genres:**")
        for genre, count in top_genres:
            lines.append(f"  - {genre}: {count} books")
    if finished:
        recent_done = sorted(
            finished, key=lambda x: x.finished_at or datetime.min, reverse=True
        )[:3]
        lines.append("\n**Recently finished:**")
        for b in recent_done:
            lines.append(f"  - {b.title} by {b.source or 'Unknown'}")

    return {"output": "\n".join(lines)}


async def handle_knowledge_stats(session: Session) -> dict:
    vstats = vocab_service.stats(session)
    rstats = rl.stats(session)
    ebook_items = [
        i for i in rl.list_all(session) if i.kind in {ItemKind.EBOOK, ItemKind.AUDIOBOOK}
    ]
    topics: set[str] = set()
    for item in rl.list_all(session):
        for tag in (item.tags or "").split(","):
            if tag.strip():
                topics.add(tag.strip())

    lines = [
        "**Knowledge base progress**\n",
        (
            f"- Reading list: {rstats['total']} items · {rstats['read']} finished "
            f"({rstats['percent_done']}%)"
        ),
        f"- Free books saved: {len(ebook_items)} ({vstats['ebooks_read']} finished)",
        f"- Vocabulary: {vstats['total_words']} words ({vstats['words_this_week']} this week)",
    ]
    if topics:
        sample = ", ".join(sorted(topics)[:12])
        lines.append(f"- Topics you're building: {sample}")
    return {"reply": "\n".join(lines)}


async def handle_log_practice(msg: str, session: Session) -> dict:
    ok, skill, minutes = is_practice_log_command(msg)
    if not ok or not skill:
        return {"reply": "What skill did you practice?"}

    entry = practice.log(session, skill=skill, minutes=minutes)
    breakdown = practice.weekly_breakdown(session, days=7)
    goal = user_config.get_int(session, "daily_practice_minutes_goal", 60)
    today = practice.today_total(session)
    hit_line = ""
    if goal > 0 and today >= goal:
        hit_line = f" Daily goal hit ({goal} min)."
    return {
        "reply": (
            f"Logged {entry.minutes} min of {entry.skill}. "
            f"You're at {breakdown['active_days']} of 7 days this week, "
            f"{breakdown['total_minutes']} min total.{hit_line}"
        )
    }


async def handle_practice_status(session: Session) -> dict:
    breakdown = practice.weekly_breakdown(session, days=7)
    today = practice.today_total(session)
    top_skill = breakdown.get("top_skill")
    top_line = ""
    if top_skill:
        top_line = (
            f" Your most-practiced skill this week: {top_skill} "
            f"({breakdown['by_skill'].get(top_skill, 0)} min)."
        )
    return {
        "reply": (
            f"This week: {breakdown['active_days']} of 7 days, "
            f"{breakdown['total_minutes']} min total. "
            f"Today: {today} min.{top_line}"
        )
    }


async def handle_config_command(msg: str, session: Session, sub_intent: str) -> dict:
    if sub_intent == "set_reading_goal":
        m = SET_READING_GOAL_RE.search(msg)
        if not m:
            return {"reply": "Try: set reading goal to 20 min"}
        user_config.set_value(session, "daily_reading_minutes_goal", m.group(1))
        return {"reply": f"Set daily reading goal to {m.group(1)} min."}
    if sub_intent == "pause_nudges":
        if STOP_NAGGING_RE.search(msg):
            until = user_config.pause_nudges(session, hours=24 * 7)
            return {
                "reply": (
                    "Got it. Pausing nudges for the week. "
                    f"Tell me 'resume nudges' when you want them back ({until.date()})."
                )
            }
        if PAUSE_NUDGES_WEEK_RE.search(msg):
            until = user_config.pause_nudges(session, hours=24 * 7)
        else:
            now = datetime.now()
            until = datetime.combine(now.date(), time.max)
            user_config.set_value(session, "nudges_paused_until", until.isoformat())
        return {"reply": f"Nudges paused until {until.strftime('%Y-%m-%d %H:%M')}."}
    if sub_intent == "resume_nudges":
        user_config.set_value(session, "nudges_paused_until", "")
        return {"reply": "Nudges resumed."}
    if sub_intent == "add_skill":
        m = ADD_SKILL_RE.search(msg)
        if not m:
            return {"reply": "Try: add skill drawing"}
        skill = m.group(2).strip().lower()
        skills = user_config.active_skills(session)
        if skill not in skills:
            skills.append(skill)
            user_config.set_active_skills(session, skills)
        return {"reply": f"Now tracking skill: {skill}."}
    if sub_intent == "remove_skill":
        m = STOP_SKILL_RE.search(msg)
        if not m:
            return {"reply": "Try: stop tracking guitar"}
        skill = m.group(2).strip().lower()
        skills = [s for s in user_config.active_skills(session) if s != skill]
        user_config.set_active_skills(session, skills)
        return {"reply": f"Stopped tracking {skill}. Existing logs stay intact."}
    if sub_intent == "set_quiet_hours":
        m = QUIET_HOURS_RE.search(msg)
        if not m:
            return {"reply": "Try: quiet hours 22 to 7"}
        start = int(m.group(1)) % 24
        end = int(m.group(2)) % 24
        user_config.set_value(session, "quiet_hours_start", f"{start:02d}:00")
        user_config.set_value(session, "quiet_hours_end", f"{end:02d}:00")
        return {"reply": f"Quiet hours set to {start:02d}:00-{end:02d}:00."}
    return {"reply": "Done."}


async def handle_chat(msg: str, history: list[dict] | None = None) -> dict:
    """Generic chat handler — no saves, no Obsidian writes."""
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    llm_messages: list[dict[str, str]] = [{"role": "system", "content": ROSS_CHAT_SYSTEM}]
    for turn in _chat_turns(history)[-8:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            llm_messages.append({"role": role, "content": content})
    llm_messages.append({"role": "user", "content": msg})
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model_cheap,
            messages=llm_messages,
        )
        _log_openai_usage(resp, settings.openai_model_cheap, "chat")
        reply = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.warning("Ross chat LLM failed: {}", e)
        reply = (
            "Okay so — I'm having a little trouble connecting right now. "
            "Give me a sec and try again?"
        )
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
    def _key(i: KnowledgeItem) -> datetime:
        if not i.published:
            return datetime.min
        if i.published.tzinfo is not None:
            return i.published.replace(tzinfo=None)
        return i.published

    return sorted(items, key=_key, reverse=True)


FRESH_CONTENT_DAYS = 21


def _item_age_days(item: KnowledgeItem) -> int | None:
    if not item.published:
        return None
    pub = item.published
    if pub.tzinfo is not None:
        pub = pub.replace(tzinfo=None)
    return max(0, (datetime.now() - pub).days)


def _prefer_fresh(
    items: list[KnowledgeItem],
    *,
    fresh_days: int = FRESH_CONTENT_DAYS,
) -> list[KnowledgeItem]:
    """Sort by date and surface recent items before older undated or stale ones."""
    sorted_items = _sort_recent(items)
    fresh = [
        i for i in sorted_items
        if _item_age_days(i) is not None and _item_age_days(i) <= fresh_days
    ]
    undated = [i for i in sorted_items if _item_age_days(i) is None]
    stale = [
        i for i in sorted_items
        if _item_age_days(i) is not None and _item_age_days(i) > fresh_days
    ]
    if fresh:
        return fresh + undated + stale
    return sorted_items


# ── Morning Brief ──────────────────────────────────────────────────────────────


async def morning_section() -> str:
    """Curate a 3-item brief and return rendered Markdown (no file write).

    Exposed for the unified combined-brief job. Returns the `## 🪄 Ross's Picks`
    section as a string.
    """
    settings = get_settings()

    with next(get_session()) as session:
        recent_tags = _top_tags_from_reading_list(session)

    candidates = await _fetch_digest_candidates(
        interests=settings.interest_list,
        recent_tags=recent_tags,
        include_web=True,
    )
    if not candidates:
        logger.warning("Morning brief: no candidates found")
        return "## 🪄 Ross's Picks\n\n_No items found today._\n"

    profile = await _get_github_profile()
    cand_lines = []
    for i, c in enumerate(candidates[:30], 1):
        tag_note = f" · {c.genre}" if c.genre else ""
        cand_lines.append(
            f"{i}. [{c.source}{tag_note}] {c.title} ({_format_date(c.published)}) — "
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
        _log_openai_usage(resp, settings.openai_model_main, "morning_brief")
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
        date_label = item.get("date", "")
        blurb = item.get("blurb", "")
        link = f"[{title}]({url})" if url else title
        meta = " · ".join(filter(None, [source, date_label]))
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
    attachments = state.get("attachments", []) or []
    history = state.get("chat_history") or []
    lowered = msg.strip().lower()
    sub_intent = classify_sub_intent(msg, attachments, history)

    # Ensure DB is ready (idempotent)
    init_db()

    with next(get_session()) as session:
        pending = pending_actions.peek_pending()
        if pending and pending.kind == "delete_reading_item" and lowered in {"yes", "no"}:
            return await handle_delete_confirm(session, confirm=lowered == "yes")

        if sub_intent == "save":
            return await handle_save(msg, session, attachments=attachments, history=history)
        if sub_intent == "list":
            return await handle_list(msg, session)
        if sub_intent == "mark_read":
            _, target = is_mark_command(msg)
            return await handle_mark_read(target, session)
        if sub_intent == "update_progress":
            _, pct, target = is_progress_command(msg)
            return await handle_progress(target, pct, session)
        if sub_intent == "delete":
            _, target = is_delete_command(msg)
            if not target:
                return {"reply": "What should I remove from your list?"}
            return await handle_delete(target, session)
        if sub_intent == "clear_list":
            return await handle_clear_list(session)
        if sub_intent == "confirm_clear_list":
            return await handle_confirm_clear_list(session)
        if sub_intent == "query":
            return await handle_query(msg, session)
        if sub_intent == "suggest":
            return await handle_suggest(msg, session, history=history)
        if sub_intent == "log_practice":
            return await handle_log_practice(msg, session)
        if sub_intent == "practice_status":
            return await handle_practice_status(session)
        if sub_intent == "find_book":
            return await handle_find_book(msg, session, history=history)
        if sub_intent == "research_search":
            return await handle_research_search(msg, session)
        if sub_intent == "topic_search":
            return await handle_topic_search(msg, session, history)
        if sub_intent == "download_book":
            if "audiobook" in lowered:
                return await handle_download_audiobook(msg, session)
            return await handle_download_book(msg, session, history=history)
        if sub_intent == "log_vocab":
            return await handle_log_vocab(msg, session)
        if sub_intent == "list_vocab":
            return await handle_list_vocab(msg, session)
        if sub_intent == "knowledge_stats":
            return await handle_knowledge_stats(session)
        if sub_intent == "apple_books":
            return await handle_apple_books_from_db(msg, session)
        if sub_intent in {
            "set_reading_goal",
            "pause_nudges",
            "resume_nudges",
            "add_skill",
            "remove_skill",
            "set_quiet_hours",
        }:
            return await handle_config_command(msg, session, sub_intent)
        if "what can you do" in lowered:
            stats = rl.stats(session)
            q = (
                " and ".join([s for s in user_config.active_skills(session)[:2]])
                or "your active skills"
            )
            return {
                "reply": (
                    "Here's what I can do:\n"
                    f"- `save in notes <url>` -> fetch and summarize it\n"
                    f"- `show my reading list` -> {stats['total']} items right now\n"
                    "- `find free books on stoicism` -> search Gutenberg + Open Library\n"
                    "- `download Meditations` -> free public-domain ebook to your list\n"
                    "- `log vocab: word — definition` -> track vocabulary as you read\n"
                    "- `knowledge stats` -> reading + vocab progress\n"
                    "- `what am I reading in Apple Books?` -> in-progress + highlights\n"
                    "- `what do I know about <topic>` -> search your notes and reading history\n"
                    f"- `I practiced {q} for 20 min` -> log practice toward your goals\n"
                    "- `suggest me a few things to read today` -> "
                    "pick 3 with summaries, add from chat\n"
                    "- Anything else, I'll chat without auto-saving."
                )
            }

    if sub_intent == "digest_now":
        return await handle_digest_now(msg, history=history)
    if sub_intent == "summarize_url":
        return await handle_summarize_url(msg)
    return await handle_chat(msg, history)
