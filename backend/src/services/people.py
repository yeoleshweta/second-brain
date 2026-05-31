"""People service — markdown-backed person notes in 04-People/.

Each person lives in a single file: <vault>/04-People/<First-Last>.md
YAML frontmatter holds structured data; body holds freeform notes.
This module never overwrites the body — only touches frontmatter and the
"## Interactions" section appended at the bottom.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import frontmatter

from src.config import get_settings

PEOPLE_DIR = "04-People"


def _vault_path() -> Path:
    s = get_settings()
    if not s.obsidian_vault_path:
        raise RuntimeError("OBSIDIAN_VAULT_PATH not set in environment")
    p = Path(s.obsidian_vault_path) / PEOPLE_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def slugify(name: str) -> str:
    """'Sarah Wong' → 'Sarah-Wong'"""
    return re.sub(r"[^a-zA-Z0-9]+", "-", name.strip()).strip("-")


def _read_person(path: Path) -> dict:
    """Parse a person markdown file into {filename, path, frontmatter, body}."""
    post = frontmatter.load(str(path))
    return {
        "filename": path.name,
        "path": path,
        "frontmatter": dict(post.metadata),
        "body": post.content,
        "body_preview": post.content[:200].strip(),
    }


def list_all() -> list[dict]:
    """Return all person notes as parsed dicts."""
    try:
        people_dir = _vault_path()
    except RuntimeError:
        return []
    return [_read_person(p) for p in sorted(people_dir.glob("*.md"))]


def find(name_query: str) -> list[dict]:
    """Fuzzy case-insensitive match against `name` frontmatter field and filename."""
    q = name_query.strip().lower()
    results = []
    for person in list_all():
        fm_name = str(person["frontmatter"].get("name", "")).lower()
        file_stem = Path(person["filename"]).stem.replace("-", " ").lower()
        if q in fm_name or q in file_stem:
            results.append(person)
    return results


def find_by_file_path(file_path: Path) -> dict | None:
    """Return the parsed person dict for a specific file, or None."""
    if not file_path.exists():
        return None
    return _read_person(file_path)


def create(name: str, **fm_fields: Any) -> Path:
    """Create a new person note. Returns the file Path."""
    people_dir = _vault_path()
    slug = slugify(name)
    file_path = people_dir / f"{slug}.md"

    today = date.today().isoformat()
    metadata: dict[str, Any] = {
        "name": name,
        "emails": [],
        "company": "",
        "role": "",
        "location": "",
        "tags": [],
        "first_contacted": today,
        "last_contacted": today,
        "last_interaction": "",
    }
    metadata.update(fm_fields)

    post = frontmatter.Post(content="", **metadata)
    file_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return file_path


def update_frontmatter(file_path: Path, updates: dict[str, Any]) -> None:
    """Merge `updates` into frontmatter while preserving the body."""
    post = frontmatter.load(str(file_path))
    for key, value in updates.items():
        post.metadata[key] = value
    file_path.write_text(frontmatter.dumps(post), encoding="utf-8")


def log_interaction(
    file_path: Path,
    summary: str,
    on_date: date | None = None,
) -> None:
    """Append a dated bullet to the ## Interactions section.

    Also updates `last_contacted` and `last_interaction` in frontmatter.
    """
    entry_date = (on_date or date.today()).isoformat()
    bullet = f"- **{entry_date}** — {summary}"

    post = frontmatter.load(str(file_path))
    body = post.content

    if "## Interactions" in body:
        body = body + f"\n{bullet}"
    else:
        body = body.rstrip() + f"\n\n## Interactions\n\n{bullet}"

    post.content = body
    post.metadata["last_contacted"] = entry_date
    post.metadata["last_interaction"] = summary
    file_path.write_text(frontmatter.dumps(post), encoding="utf-8")


def get_summary(person: dict) -> str:
    """Build a human-readable summary from frontmatter + body preview."""
    fm = person["frontmatter"]
    lines = []
    if fm.get("name"):
        lines.append(f"**{fm['name']}**")
    parts = []
    if fm.get("role"):
        parts.append(fm["role"])
    if fm.get("company"):
        parts.append(f"at {fm['company']}")
    if parts:
        lines.append(", ".join(parts))
    if fm.get("location"):
        lines.append(f"📍 {fm['location']}")
    if fm.get("last_contacted"):
        lines.append(f"Last contacted: {fm['last_contacted']}")
    if fm.get("last_interaction"):
        lines.append(f"Last interaction: {fm['last_interaction']}")
    if fm.get("tags"):
        tags = fm["tags"] if isinstance(fm["tags"], list) else [fm["tags"]]
        lines.append("Tags: " + ", ".join(str(t) for t in tags))
    preview = person.get("body_preview", "").strip()
    if preview:
        lines.append(f"\n{preview}")
    return "\n".join(lines)


def days_since_contacted(person: dict) -> int | None:
    """Return days since last_contacted, or None if never recorded."""
    last = person["frontmatter"].get("last_contacted")
    if not last:
        return None
    try:
        last_dt = datetime.fromisoformat(str(last)).date()
        return (date.today() - last_dt).days
    except (ValueError, TypeError):
        return None
