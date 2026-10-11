"""LLM Wiki ingest + human review. Nothing leaves Inbox until you approve."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import frontmatter
from loguru import logger

from src.config import get_settings
from src.integrations.obsidian import SYSTEM_LOG_DIR, ObsidianClient

INBOX_DIR = "Inbox"
WIKI_DEST_PREFIXES = ("Notes/", "People/", "Projects/", "Concepts/", "Briefings/")
ReviewStatus = Literal["inbox", "proposed", "processed", "rejected"]

PROCESSING_PROMPT = """You are a knowledge management assistant.
Process the following raw note and return a JSON object with these fields:

- "summary": A 2-3 sentence summary of the main idea
- "key_concepts": Array of 3-7 core concepts mentioned
- "people": Array of any people referenced
- "action_items": Array of any tasks or follow-ups mentioned
- "related_topics": Array of topics this note connects to
- "destination_folder": One of Notes, People, Projects, Concepts
- "destination_title": Short filename title without .md
- "processed_content": The full note rewritten in clean Markdown with:
  - A clear H2 heading
  - Summary section
  - Key points as bullets
  - [[wiki-links]] for concepts, people, or projects that should have their own notes

This is a PROPOSAL only. A human must approve before it is filed.

Raw note:
{content}

Return only valid JSON. No additional text."""


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "note").lower()).strip("-")
    return (slug or "note")[:72]


def _now() -> datetime:
    return datetime.now()


def _iso_date(now: datetime | None = None) -> str:
    return (now or _now()).strftime("%Y-%m-%d")


def _assert_wiki_destination(path: str) -> None:
    normalized = path.replace("\\", "/").lstrip("/")
    if not any(normalized == p.rstrip("/") or normalized.startswith(p) for p in WIKI_DEST_PREFIXES):
        raise PermissionError(f"Refusing wiki destination (review folders only): {path}")
    if ".." in normalized.split("/"):
        raise PermissionError(f"Refusing wiki destination: {path}")


def _vault_root() -> Path:
    settings = get_settings()
    if not settings.obsidian_vault_path:
        raise RuntimeError("OBSIDIAN_VAULT_PATH is not set")
    return Path(settings.obsidian_vault_path)


def _dump(post: frontmatter.Post) -> str:
    return frontmatter.dumps(post).rstrip() + "\n"


def build_inbox_markdown(
    *,
    title: str,
    body: str,
    source: str,
    status: ReviewStatus = "inbox",
    destination: str = "",
    proposed: str = "",
    extra: dict[str, Any] | None = None,
) -> str:
    now = _now()
    created = now.strftime("%Y-%m-%dT%H:%M")
    meta: dict[str, Any] = {
        "title": title,
        "date_created": _iso_date(now),
        "date_modified": _iso_date(now),
        "tags": [],
        "status": status,
        "related": [],
        "source": source,
        "destination": destination,
    }
    if extra:
        meta.update(extra)
    content = f"## Raw\n\n{body.strip()}\n"
    if proposed.strip():
        content += f"\n## Proposed\n\n{proposed.strip()}\n"
    post = frontmatter.Post(content, **meta)
    post.metadata["date_modified"] = created[:10]
    return _dump(post)


def parse_inbox(raw: str) -> frontmatter.Post:
    return frontmatter.loads(raw)


def split_raw_proposed(body: str) -> tuple[str, str]:
    text = body or ""
    if "## Proposed" in text:
        raw_part, _, prop = text.partition("## Proposed")
        raw_part = raw_part.replace("## Raw", "", 1).strip()
        return raw_part, prop.strip()
    return text.replace("## Raw", "", 1).strip(), ""


async def ingest_raw(*, title: str, body: str, source: str) -> str:
    """Write Inbox/{date}-{slug}.md with status inbox. Never files wiki folders."""
    now = _now()
    slug = slugify(title)
    rel = f"{INBOX_DIR}/{now.strftime('%Y-%m-%d')}-{now.strftime('%H%M%S')}-{slug}.md"
    md = build_inbox_markdown(title=title.strip() or slug, body=body, source=source)
    async with ObsidianClient() as client:
        await client.create_note(rel, md)
    logger.info("Wiki ingest → {}", rel)
    return rel


async def get_item(rel_path: str) -> dict[str, Any]:
    normalized = rel_path.replace("\\", "/").lstrip("/")
    if not normalized.startswith(f"{INBOX_DIR}/") or ".." in normalized.split("/"):
        raise PermissionError("can only read Inbox notes")
    async with ObsidianClient() as client:
        raw_md = await client.get_note(normalized)
    post = parse_inbox(raw_md)
    raw, proposed = split_raw_proposed(post.content)
    return {
        "path": normalized,
        "title": post.get("title") or normalized,
        "status": str(post.get("status") or "inbox"),
        "source": post.get("source") or "",
        "destination": post.get("destination") or "",
        "summary": post.get("summary") or "",
        "raw": raw,
        "proposed": proposed,
        "date_created": post.get("date_created") or "",
    }


async def list_pending() -> list[dict[str, Any]]:
    root = _vault_root()
    inbox = root / INBOX_DIR
    if not inbox.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(inbox.glob("*.md")):
        post = parse_inbox(path.read_text(encoding="utf-8"))
        status = str(post.get("status") or "inbox")
        if status not in {"inbox", "proposed"}:
            continue
        raw, proposed = split_raw_proposed(post.content)
        rel = f"{INBOX_DIR}/{path.name}"
        out.append(
            {
                "path": rel,
                "title": post.get("title") or path.stem,
                "status": status,
                "source": post.get("source") or "",
                "destination": post.get("destination") or "",
                "summary": post.get("summary") or "",
                "raw_excerpt": raw[:400],
                "proposed_excerpt": proposed[:400],
                "raw": raw,
                "proposed": proposed,
                "date_created": post.get("date_created") or "",
            }
        )
    return out


async def _log_failure(detail: str) -> None:
    now = _now()
    path = f"{SYSTEM_LOG_DIR}/{now.strftime('%Y-%m-%d')}.md"
    line = f"- {now.strftime('%H:%M')} {detail}\n"
    try:
        async with ObsidianClient() as client:
            try:
                existing = await client.get_note(path)
                await client.create_note(path, existing.rstrip() + "\n" + line)
            except Exception:
                await client.create_note(path, f"# {now.strftime('%Y-%m-%d')}\n\n{line}")
    except Exception as exc:
        logger.warning("wiki failure log skipped: {}", type(exc).__name__)


async def propose(rel_path: str) -> dict[str, Any]:
    """Ask Claude to draft a filing. Status becomes proposed. Does not write Notes/."""
    from src.integrations.claude import complete, parse_json_object

    async with ObsidianClient() as client:
        raw_md = await client.get_note(rel_path)
    post = parse_inbox(raw_md)
    raw, _ = split_raw_proposed(post.content)
    try:
        text = await complete(
            system="Return only JSON. This is a filing proposal; a human will approve it.",
            user=PROCESSING_PROMPT.format(content=raw[:12000]),
            max_tokens=4096,
        )
        data = parse_json_object(text)
    except Exception as exc:
        logger.warning("wiki propose failed: {}", type(exc).__name__)
        await _log_failure(f"wiki propose failed ({rel_path}): {type(exc).__name__}")
        raise

    folder = str(data.get("destination_folder") or "Notes").strip().strip("/")
    if folder not in {"Notes", "People", "Projects", "Concepts"}:
        folder = "Notes"
    dest_title = str(data.get("destination_title") or post.get("title") or "note")
    destination = f"{folder}/{slugify(dest_title)}.md"
    _assert_wiki_destination(destination)
    processed = str(data.get("processed_content") or "").strip()
    post.metadata["status"] = "proposed"
    post.metadata["destination"] = destination
    post.metadata["summary"] = data.get("summary") or ""
    post.metadata["related"] = data.get("related_topics") or data.get("key_concepts") or []
    post.metadata["date_modified"] = _iso_date()
    post.content = f"## Raw\n\n{raw.strip()}\n\n## Proposed\n\n{processed}\n"
    async with ObsidianClient() as client:
        await client.create_note(rel_path, _dump(post))
    return {
        "path": rel_path,
        "status": "proposed",
        "destination": destination,
        "summary": post.metadata.get("summary"),
        "proposal": data,
    }


async def approve(rel_path: str, destination: str | None = None) -> dict[str, Any]:
    """Human said yes — write the proposed note into a wiki folder."""
    async with ObsidianClient() as client:
        raw_md = await client.get_note(rel_path)
    post = parse_inbox(raw_md)
    if str(post.get("status")) == "rejected":
        raise ValueError("cannot approve a rejected note")
    raw, proposed = split_raw_proposed(post.content)
    dest = (destination or str(post.get("destination") or "")).replace("\\", "/").lstrip("/")
    if not proposed.strip():
        raise ValueError("no proposal to approve — run propose first")
    _assert_wiki_destination(dest)
    filed = (
        f"---\n"
        f"title: {json.dumps(str(post.get('title') or dest))}\n"
        f"date_created: {post.get('date_created') or _iso_date()}\n"
        f"date_modified: {_iso_date()}\n"
        f"tags: []\n"
        f"status: processed\n"
        f"related: {json.dumps(post.get('related') or [])}\n"
        f"source: {post.get('source') or 'chat'}\n"
        f"inbox: {rel_path}\n"
        f"---\n\n"
        f"{proposed.strip()}\n"
    )
    post.metadata["status"] = "processed"
    post.metadata["destination"] = dest
    post.metadata["date_modified"] = _iso_date()
    post.content = f"## Raw\n\n{raw.strip()}\n\n## Proposed\n\n{proposed.strip()}\n"
    async with ObsidianClient() as client:
        await client.create_note(dest, filed)
        await client.create_note(rel_path, _dump(post))
    logger.info("Wiki approved {} → {}", rel_path, dest)
    return {"path": rel_path, "status": "processed", "destination": dest}


async def reject(rel_path: str) -> dict[str, Any]:
    async with ObsidianClient() as client:
        raw_md = await client.get_note(rel_path)
    post = parse_inbox(raw_md)
    post.metadata["status"] = "rejected"
    post.metadata["date_modified"] = _iso_date()
    async with ObsidianClient() as client:
        await client.create_note(rel_path, _dump(post))
    return {"path": rel_path, "status": "rejected"}


def title_from_message(message: str) -> str:
    t = (message or "").strip().split("\n", 1)[0]
    t = re.sub(r"\s+", " ", t)
    return (t[:72] if t else "Chat capture").strip()
