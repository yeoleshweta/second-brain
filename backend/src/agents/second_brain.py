"""One Second Brain agent — Claude chat; wiki filing waits for human review."""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from src.config import get_settings

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState

SYSTEM_PROMPT = """You are Eleven. This is the only voice.
There is no separate personality to set up.

Speak in short sentences. Simple words. Present tense. Quiet, warm, direct.
Call them a friend when it fits. Do not stack catchphrases.
Do not mention Eggos, the Upside Down, or powers unless they do.

Read the whole sentence, including lists and half-thoughts.
Decide what they mean from this message and the recent chat, then answer that.
"This" and "these" mean what they just said.
If this chat has no earlier turn, "just" means the newest lines in today's file.

Facts about their life come only from the capture outcome, today's files,
matching older notes, and the recent chat.
If those do not contain a fact, say you do not have it.
Do not invent notes, meetings, emails, or a save.

Do not say you saved, logged, filed, or scheduled anything.
Never write a Status heading. The app adds the only status line after your reply.
Do not repeat that line or contradict it.
When a matching note is useful, name its title.

Calendar, reminders, and mail are answered before you run, for the phrases
"what's on my calendar", "my meetings", "unread email", "organize my day",
and "remind me on October 20 at 9am to …".
Do not say you cannot set a reminder. Do not invent meetings or mail.
Do not send email. Do not file notes. Filing happens only after they approve in Review."""

_NOTE_ROOTS = ("Notes", "People", "Projects", "Concepts", "Briefings", "00-Inbox", "Inbox")
_SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules"}
_STOP = frozenset(
    {
        "the", "a", "an", "to", "and", "or", "of", "in", "on", "for", "with",
        "this", "that", "you", "your", "my", "me", "we", "it", "is", "are", "was",
        "be", "remember", "write", "down", "capture", "note", "inbox", "today",
        "what", "how", "why", "when", "where", "who", "from", "about", "just",
        "like", "into", "have", "has", "want", "need", "does",
    }
)


def _build_system_message(
    pending_blurb: str,
    vault_ctx: str,
    *,
    capture_outcome: str,
    matches: str,
) -> str:
    parts = [
        SYSTEM_PROMPT,
        "This turn's capture outcome (do not restate it):\n" + capture_outcome.strip(),
    ]
    if matches.strip():
        parts.append("Matching older notes:\n" + matches[:4000])
    if vault_ctx.strip():
        parts.append("Today's vault (read only):\n" + vault_ctx[:4000])
    if pending_blurb.strip():
        parts.append("Notes waiting for review:\n" + pending_blurb[:1500])
    return "\n\n".join(parts)


def _query_terms(message: str) -> list[str]:
    from src.integrations.obsidian import _strip_capture_prefix

    words = re.findall(r"[a-z0-9]{3,}", _strip_capture_prefix(message).lower())
    terms: list[str] = []
    for word in words:
        if word in _STOP or word in terms:
            continue
        terms.append(word)
        if len(terms) == 6:
            break
    return terms


def _snippet(text: str, term: str) -> str:
    low = text.lower()
    at = low.find(term)
    if at < 0:
        return text[:400].strip()
    start = max(0, at - 80)
    return text[start : start + 400].strip()


def _local_matches(root: Path, terms: list[str], exclude: str | None) -> list[tuple[str, str]]:
    files: list[Path] = []
    for prefix in _NOTE_ROOTS:
        base = root / prefix
        if not base.exists():
            continue
        for path in base.rglob("*.md"):
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            files.append(path)
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    scored: list[tuple[int, str, str]] = []
    for path in files[:120]:
        rel = path.relative_to(root).as_posix()
        if exclude and rel == exclude:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        score = sum(text.lower().count(term) for term in terms)
        if any(term in path.name.lower() for term in terms):
            score += 4
        if score:
            scored.append((score, rel, _snippet(text, terms[0])))
    scored.sort(key=lambda row: row[0], reverse=True)
    return [(rel, snip) for _, rel, snip in scored[:3]]


def _format_matches(rows: list[tuple[str, str]]) -> str:
    return "\n\n".join(f"--- {rel} ---\n{snip}" for rel, snip in rows)


async def _matching_notes(message: str, exclude: str | None) -> str:
    terms = _query_terms(message)
    if not terms:
        return ""
    settings = get_settings()
    root = settings.obsidian_vault_path
    if root and Path(root).exists():
        rows = await asyncio.to_thread(_local_matches, Path(root), terms, exclude)
        return _format_matches(rows)

    from src.integrations.obsidian import ObsidianClient

    rows: list[tuple[str, str]] = []
    try:
        async with ObsidianClient() as client:
            for folder in ("People", "Projects", "Concepts", "Notes", "Briefings"):
                try:
                    names = await client.list_folder(folder)
                except Exception:
                    continue
                for name in names:
                    if name.endswith("/") or not name.lower().endswith(".md"):
                        continue
                    if not any(term in name.lower() for term in terms):
                        continue
                    rel = f"{folder}/{name}"
                    if exclude and rel == exclude:
                        continue
                    try:
                        text = await client.get_note(rel)
                    except Exception:
                        continue
                    rows.append((rel, _snippet(text, terms[0])))
                    if len(rows) >= 3:
                        return _format_matches(rows)
    except Exception as exc:
        logger.debug("note search skipped: {}", type(exc).__name__)
    return _format_matches(rows)


async def _pending_blurb() -> str:
    try:
        from src.services.wiki import list_pending

        rows = await list_pending()
    except Exception as exc:
        logger.debug("pending review list skipped: {}", type(exc).__name__)
        return ""
    if not rows:
        return ""
    lines = [
        f"- `{r['path']}` ({r['status']}) → {r.get('destination') or 'no destination yet'}"
        for r in rows[:12]
    ]
    return "\n".join(lines)


async def _today_vault_context() -> str:
    from datetime import datetime

    from src.integrations.obsidian import DAILY_NOTE_DIR, VOID_DIR, ObsidianClient

    today = datetime.now().strftime("%Y-%m-%d")
    chunks: list[str] = []
    try:
        async with ObsidianClient() as client:
            for rel in (f"{VOID_DIR}/{today}.md", f"{DAILY_NOTE_DIR}/{today}.md"):
                try:
                    text = await client.get_note(rel)
                except Exception:
                    continue
                body = text.strip()
                if body:
                    if len(body) > 3000:
                        body = body[-3000:]
                    chunks.append(f"--- {rel} (newest at the end) ---\n{body}")
    except Exception as exc:
        logger.debug("today vault context skipped: {}", type(exc).__name__)
    return "\n\n".join(chunks)


async def _capture_status(message: str) -> tuple[str, str | None]:
    from src.agents._base import is_inbox_capture
    from src.integrations.obsidian import (
        ObsidianClient,
        _strip_capture_prefix,
        classify_log_type,
        unsorted_reason,
    )

    if not is_inbox_capture(message):
        return None, None
    try:
        async with ObsidianClient() as client:
            path = await client.append_to_inbox(message, source="user")
    except Exception as exc:
        logger.warning("Void capture failed: {}", type(exc).__name__)
        try:
            from src.services.retry_queue import enqueue

            enqueue(message)
        except Exception:
            logger.warning("retry queue write failed")
        return ("Not saved yet. It is queued and will be written again.", None)
    cleaned = _strip_capture_prefix(message)
    typ = classify_log_type(cleaned)
    if typ:
        return (f"Saved under Log in `{path}` as {typ}.", path)
    return (
        f"Saved under Unsorted in `{path}` ({unsorted_reason(cleaned)}).",
        path,
    )


async def run(state: AgentState) -> dict:
    from src.integrations.claude import complete, public_claude_error
    from src.services.calendar_chat import maybe_handle

    settings = get_settings()
    message = state["user_message"]
    status, path = await _capture_status(message)
    calendar = await maybe_handle(message)
    if calendar is not None:
        if status:
            calendar["reply"] = f"{calendar['reply'].rstrip()}\n\n{status}"
            calendar["obsidian_path"] = path
        return calendar
    pending = await _pending_blurb()
    vault_ctx = await _today_vault_context()
    matches = await _matching_notes(state["user_message"], path)
    history = [
        {"role": str(t.get("role")), "content": str(t.get("content"))}
        for t in (state.get("chat_history") or [])[-8:]
        if t.get("role") in {"user", "assistant"} and t.get("content")
    ]
    try:
        if not settings.anthropic_key_present:
            reply = (
                "ANTHROPIC_API_KEY is not set. Add it to backend/.env and restart. "
                "Your message can still be saved to Inbox for review."
            )
        else:
            system = _build_system_message(
                pending,
                vault_ctx,
                capture_outcome=status
                or "Not a capture. Answer the question. Do not mention saving or a status line.",
                matches=matches,
            )
            if (state.get("metadata") or {}).get("plain_mode"):
                system += (
                    "\nPLAIN_MODE is on. Drop Eleven's voice. "
                    "Use plain sentences only."
                )
            reply = await complete(
                system=system,
                user=state["user_message"],
                messages=history,
                max_tokens=1024,
            ) or "I'm here. What's on your mind?"
    except Exception as exc:
        logger.warning("Second Brain Claude error: {}", type(exc).__name__)
        reply = public_claude_error(exc)

    if status:
        reply = f"{reply.rstrip()}\n\n{status}"
    return {"reply": reply, "obsidian_path": path, "intent": "general"}
