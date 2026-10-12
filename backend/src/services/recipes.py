"""Saved recipes: personal steps and YouTube links from the void files."""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

_LINE_RE = re.compile(
    r"^- (?P<time>\d{2}:\d{2}) .+ \*\*recipe\*\* :: (?P<body>.+?) \[src:: [^]]+\]\s*$",
    re.MULTILINE,
)
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_ASK_RE = re.compile(r"\b(?:recipes?|nutrition)\b", re.IGNORECASE)
_ASK_HINT_RE = re.compile(
    r"\b(?:my|show|fetch|what|saved|have|list|find|get|the)\b",
    re.IGNORECASE,
)
_STOP = frozenset(
    {
        "the", "a", "an", "to", "and", "or", "of", "in", "on", "for", "with",
        "my", "me", "what", "show", "have", "has", "saved", "save", "recipe",
        "recipes", "youtube", "fetch", "from", "that", "this", "please",
        "nutrition", "video", "link", "links",
    }
)


@dataclass
class Recipe:
    date: str
    time: str
    body: str
    path: str
    url: str
    title: str
    kind: str


def youtube_url(text: str) -> str:
    for raw in _URL_RE.findall(text or ""):
        link = raw.rstrip(".,);]>")
        host = link.lower()
        if "youtube.com" in host or "youtu.be" in host:
            return link
    return ""


async def youtube_title(url: str) -> str:
    """Public oEmbed title. Empty when YouTube does not answer."""
    if not url:
        return ""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                "https://www.youtube.com/oembed",
                params={"url": url, "format": "json"},
            )
        if response.status_code != 200:
            return ""
        title = str(response.json().get("title") or "").strip()
    except Exception:
        return ""
    return title[:140]


async def with_youtube_title(text: str) -> str:
    """Append a fetched video title when the message has a YouTube link."""
    url = youtube_url(text)
    if not url:
        return text
    title = await youtube_title(url)
    if not title or title.lower() in text.lower():
        return text
    return f"{text.rstrip()} — {title}"


def parse_recipe_file(name: str, text: str) -> list[Recipe]:
    date = name.removesuffix(".md")
    path = f"00-Inbox/Void/{name}"
    found: list[Recipe] = []
    for match in _LINE_RE.finditer(text or ""):
        body = match.group("body").strip()
        url = youtube_url(body)
        title = ""
        if " — " in body:
            title = body.split(" — ", 1)[1].strip()
        elif not url:
            title = body.split("\n", 1)[0][:80]
        found.append(
            Recipe(
                date=date,
                time=match.group("time"),
                body=body,
                path=path,
                url=url,
                title=title,
                kind="youtube" if url else "personal",
            )
        )
    return found


def _terms(message: str) -> list[str]:
    words = re.findall(r"[a-z0-9]{3,}", (message or "").lower())
    terms: list[str] = []
    for word in words:
        if word in _STOP or word in terms:
            continue
        terms.append(word)
    return terms


def select_recipes(message: str, recipes: list[Recipe]) -> tuple[list[str], list[Recipe]]:
    terms = _terms(message)
    if not terms:
        return terms, recipes[:12]
    picked = [
        item
        for item in recipes
        if any(term in f"{item.title} {item.body}".lower() for term in terms)
    ]
    return terms, picked


def format_recipe_reply(message: str, recipes: list[Recipe]) -> str:
    terms, picked = select_recipes(message, recipes)
    if terms and not picked:
        return "I don't have a saved recipe for that."
    if not picked:
        return (
            "You don't have any saved recipes yet. "
            'Say "remember this recipe" and the steps, or share a YouTube link.'
        )
    lines = ["Saved recipes:"]
    for item in picked[:8]:
        if item.kind == "youtube":
            name = (item.title or "YouTube recipe").replace("[", "").replace("]", "")
            lines.append(f"- [{name}]({item.url})")
            lines.append("  The video link is saved. The steps are not, unless you typed them.")
        else:
            name = item.title or "Recipe"
            lines.append(f"- {name} ({item.date})")
            lines.append(f"  {item.body}")
    return "\n".join(lines)


def asks_for_recipes(message: str) -> bool:
    from src.agents._base import is_inbox_capture

    text = message or ""
    if is_inbox_capture(text) or not _ASK_RE.search(text):
        return False
    return bool(_ASK_HINT_RE.search(text)) or len(text) <= 80


async def load_recipes() -> list[Recipe]:
    from src.integrations.obsidian import VOID_DIR, ObsidianClient

    try:
        async with ObsidianClient() as client:
            files = await client.read_markdown_folder(VOID_DIR)
    except Exception:
        return []
    items: list[Recipe] = []
    for name, text in files.items():
        items.extend(parse_recipe_file(name, text))
    items.sort(key=lambda item: (item.date, item.time), reverse=True)
    return items


async def maybe_recipe_reply(message: str) -> str | None:
    if not asks_for_recipes(message):
        return None
    recipes = await load_recipes()
    return format_recipe_reply(message, recipes)
