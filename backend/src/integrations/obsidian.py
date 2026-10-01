"""Obsidian integration — vault folder first, Local REST API only as fallback.

v1 capture writes markdown under OBSIDIAN_VAULT_PATH. The Local REST API
plugin is optional: if the vault folder exists, disk writes succeed even
when nothing is listening on 127.0.0.1:27124.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from loguru import logger

from src.config import get_settings


def _fs_list_dir(root: Path, folder: str) -> list[str]:
    dest = root / folder.strip("/")
    if not dest.exists() or not dest.is_dir():
        return []
    names: list[str] = []
    for child in sorted(dest.iterdir()):
        names.append(f"{child.name}/" if child.is_dir() else child.name)
    return names


def _fs_read(root: Path, path: str) -> str:
    return (root / path).read_text(encoding="utf-8")


class _RestBackend:
    """Calls the Obsidian Local REST API plugin (https://127.0.0.1:27124)."""

    def __init__(self, api_key: str, base_url: str) -> None:
        import httpx

        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15.0,
            verify=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get(self, path: str) -> str:
        resp = await self._client.get(f"/vault/{path}")
        resp.raise_for_status()
        return resp.text

    async def put(self, path: str, content: str) -> None:
        resp = await self._client.put(
            f"/vault/{path}",
            content=content.encode("utf-8"),
            headers={"Content-Type": "text/markdown"},
        )
        resp.raise_for_status()

    async def append(self, path: str, content: str) -> None:
        resp = await self._client.post(
            f"/vault/{path}",
            content=content.encode("utf-8"),
            headers={"Content-Type": "text/markdown"},
        )
        resp.raise_for_status()

    async def list_dir(self, folder: str) -> list[str]:
        prefix = folder.strip("/")
        url = f"/vault/{prefix}/" if prefix else "/vault/"
        resp = await self._client.get(url)
        resp.raise_for_status()
        data = resp.json()
        files = data.get("files") if isinstance(data, dict) else None
        if isinstance(files, list):
            return [str(f) for f in files]
        return []


class _FileBackend:
    """Writes markdown files directly to the vault directory on disk."""

    def __init__(self, vault_path: Path) -> None:
        self._root = vault_path

    async def close(self) -> None:
        pass

    def _resolve(self, path: str) -> Path:
        full = self._root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        return full

    async def get(self, path: str) -> str:
        return await asyncio.to_thread(self._resolve(path).read_text, "utf-8")

    async def put(self, path: str, content: str) -> None:
        dest = self._resolve(path)
        await asyncio.to_thread(dest.write_text, content, "utf-8")
        logger.debug("Vault write (file) → {}", dest)

    async def append(self, path: str, content: str) -> None:
        dest = self._resolve(path)

        def _append() -> None:
            with dest.open("a", encoding="utf-8") as f:
                f.write(content)

        await asyncio.to_thread(_append)
        logger.debug("Vault append (file) → {}", dest)

    async def list_dir(self, folder: str) -> list[str]:
        return await asyncio.to_thread(_fs_list_dir, self._root, folder)


def _make_backend(_rest=None, _file=None):  # type: ignore[untyped-def]
    """Build the right backend from settings.

    If the vault folder exists, write files there. A set OBSIDIAN_API_KEY
    does not require the Local REST API plugin for basic capture.
    """
    settings = get_settings()
    vault: Path | None = None
    if settings.obsidian_vault_path:
        vault = Path(settings.obsidian_vault_path)
        if not vault.exists():
            vault.mkdir(parents=True, exist_ok=True)
    if vault is not None:
        logger.debug("ObsidianClient: using filesystem at {}", vault)
        return _FileBackend(vault)
    if settings.obsidian_api_key:
        logger.debug("ObsidianClient: using REST API at {}", settings.obsidian_base_url)
        return _RestBackend(settings.obsidian_api_key, settings.obsidian_base_url)
    raise RuntimeError(
        "Obsidian not configured: set OBSIDIAN_VAULT_PATH (preferred) or OBSIDIAN_API_KEY."
    )


# v1 capture contract: bot writes 00-Inbox (Daily / Unsorted) and 99-System/Logs only.
# 01–05 are filed by hand during review. Career/Profile and Context are user-owned.
_PROTECTED_WRITE_PREFIXES = (
    "01-Knowledge",
    "02-Health",
    "03-Finance",
    "04-People",
    "05-Calendar",
    "Career/Profile",
    "Context",
)

DAILY_NOTE_DIR = "00-Inbox/Daily"
UNSORTED_DIR = "00-Inbox/Unsorted"
SYSTEM_LOG_DIR = "99-System/Logs"
DAILY_TEMPLATE_PATH = "99-System/Templates/tpl-daily.md"

LogType = Literal["food", "finance", "idea", "task", "exercise"]

_TYPE_EMOJI: dict[LogType, str] = {
    "food": "🍽",
    "finance": "💸",
    "idea": "💡",
    "task": "✅",
    "exercise": "🏃",
}

# Cheap keyword heuristic — exactly one hit files to Daily; else Unsorted.
_TYPE_KEYWORDS: dict[LogType, tuple[str, ...]] = {
    "food": (
        "ate",
        "eaten",
        "breakfast",
        "lunch",
        "dinner",
        "snack",
        "meal",
        "calories",
        "food",
        "coffee",
    ),
    "finance": (
        "spent",
        "paid",
        "bought",
        "groceries",
        "receipt",
        "budget",
        "expense",
        "dollar",
        "$",
    ),
    "idea": ("idea", "insight", "realized"),
    "task": ("todo", "to-do", "task", "remind me", "need to", "follow up", "meeting"),
        "exercise": (
            "workout",
            "gym",
            "exercise",
            "yoga",
            "walked",
            "walk",
            "jog",
            "run ",
        ),
}

_CAPTURE_PREFIX_RE = re.compile(
    r"^(?:\[(?P<agent>[^\]]+)\]\s*)?"
    r"(?:remember this|capture this|note this|dump this|"
    r"write this down|put this in (?:my )?inbox|add to inbox|inbox this)"
    r"\s*[:\—\–\-]\s*",
    re.IGNORECASE,
)


def _assert_writable(path: str) -> None:
    """Refuse writes to 01–05, Career/Profile, and Context."""
    normalized = path.replace("\\", "/").lstrip("/")
    for prefix in _PROTECTED_WRITE_PREFIXES:
        if normalized == prefix or normalized.startswith(f"{prefix}/"):
            raise PermissionError(f"Refusing to write protected vault path: {path}")


def _src_value(source: str) -> str:
    raw = (source or "user").strip().lower()
    if raw in {"user", "chat"} or raw.startswith("chat"):
        return "user"
    if raw in {"bot", "receipt"}:
        return raw
    if raw.startswith("agent") or raw.startswith("bot"):
        return "bot"
    return "user"


def _strip_capture_prefix(message: str) -> str:
    stripped = _CAPTURE_PREFIX_RE.sub("", message or "").strip()
    return stripped or (message or "").strip()


def _keyword_hit(text: str, keyword: str) -> bool:
    if keyword == "$" or not re.search(r"[A-Za-z0-9]", keyword):
        return keyword in text
    return bool(re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text))


def classify_log_type(text: str) -> LogType | None:
    """Return a single log type when keywords are unambiguous; else None."""
    lowered = (text or "").lower()
    hits: list[LogType] = []
    for typ, keywords in _TYPE_KEYWORDS.items():
        if any(_keyword_hit(lowered, kw) for kw in keywords):
            hits.append(typ)
    if len(hits) == 1:
        return hits[0]
    return None


def _format_log_entry(text: str, typ: LogType, src: str) -> str:
    ts = datetime.now().strftime("%H:%M")
    return f"- {ts} {_TYPE_EMOJI[typ]} **{typ}** :: {text} [src:: {src}]"


def _builtin_daily_note(today: str, created: str) -> str:
    return (
        f"---\n"
        f"type: daily\n"
        f"date: {today}\n"
        f"created: {created}\n"
        f"mood:\n"
        f"energy:\n"
        f"---\n\n"
        f"# {today}\n\n"
        f"## Log\n"
        f"<!-- bot appends here, newest at bottom -->\n\n"
        f"## Notes\n"
        f"<!-- your own free writing -->\n\n"
        f"## Review\n"
        f"- [ ] Triage captures\n"
    )


def _render_daily_template(raw: str, today: str, created: str) -> str:
    out = raw
    out = re.sub(r'<%\s*tp\.date\.now\("YYYY-MM-DD\[T\]HH:mm"\)\s*%>', created, out)
    out = re.sub(r'<%\s*tp\.date\.now\("YYYY-MM-DD"\)\s*%>', today, out)
    return out.replace("{{created}}", created).replace("{{date}}", today)


def _insert_under_heading(content: str, heading: str, entry_line: str) -> str:
    """Insert a new line under `heading` (before the next ##). Existing lines stay."""
    entry = entry_line.rstrip("\n") + "\n"
    body = content if content.endswith("\n") or not content else content + "\n"
    lines = body.splitlines(keepends=True)
    target = heading.strip()
    heading_idx: int | None = None
    for i, line in enumerate(lines):
        if line.strip() == target:
            heading_idx = i
            break
    if heading_idx is None:
        return body + f"\n{target}\n{entry}"
    next_idx: int | None = None
    for i in range(heading_idx + 1, len(lines)):
        if lines[i].startswith("## ") and lines[i].strip() != target:
            next_idx = i
            break
    if next_idx is None:
        return "".join(lines) + entry
    return "".join(lines[:next_idx]) + entry + "".join(lines[next_idx:])


def _lines_preserved(before: str, after: str) -> bool:
    old = [ln.rstrip("\n") for ln in before.splitlines()]
    new = [ln.rstrip("\n") for ln in after.splitlines()]
    cursor = 0
    for line in old:
        try:
            cursor = new.index(line, cursor) + 1
        except ValueError:
            return False
    return True


class ObsidianClient:
    """Async context manager that reads/writes the Obsidian vault.

    Writes the vault folder on disk when OBSIDIAN_VAULT_PATH is set.
    Local REST API is used only when there is no vault folder.
    """

    def __init__(self) -> None:
        self._backend = _make_backend()

    async def close(self) -> None:
        await self._backend.close()

    async def __aenter__(self) -> ObsidianClient:
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    async def get_note(self, path: str) -> str:
        return await self._backend.get(path)

    async def read_note(self, path: str) -> str:
        """Alias for get_note — vault-contract name."""
        return await self.get_note(path)

    async def create_note(self, path: str, content: str) -> None:
        _assert_writable(path)
        logger.info("Obsidian create {}", path)
        await self._backend.put(path, content)

    async def write_note(self, path: str, content: str) -> None:
        """Alias for create_note — vault-contract name. Overwrites."""
        await self.create_note(path, content)

    async def append_to_note(self, path: str, content: str) -> None:
        _assert_writable(path)
        logger.info("Obsidian append {}", path)
        try:
            await self._backend.append(path, content)
        except Exception:
            await self._backend.put(path, content)

    async def list_folder(self, folder: str) -> list[str]:
        """Return names in a vault folder (directories end with `/`)."""
        try:
            return await self._backend.list_dir(folder)
        except Exception as exc:
            logger.warning("list_folder via backend failed ({}): {}", folder, exc)
            settings = get_settings()
            if settings.obsidian_vault_path:
                return await asyncio.to_thread(
                    _fs_list_dir, Path(settings.obsidian_vault_path), folder
                )
            raise

    async def read_markdown_folder(self, folder: str) -> dict[str, str]:
        """Read every `.md` file in a folder. Missing folder → empty dict."""
        names = await self.list_folder(folder)
        out: dict[str, str] = {}
        prefix = folder.strip("/")
        for name in names:
            if name.endswith("/") or not name.lower().endswith(".md"):
                continue
            rel = f"{prefix}/{name}" if prefix else name
            try:
                out[name] = await self.read_note(rel)
            except Exception as exc:
                logger.warning("read_note failed for {}: {}", rel, exc)
                settings = get_settings()
                if settings.obsidian_vault_path:
                    path = Path(settings.obsidian_vault_path) / rel
                    if path.exists():
                        root = Path(settings.obsidian_vault_path)
                        out[name] = await asyncio.to_thread(_fs_read, root, rel)
        return out

    async def _log_system_failure(self, detail: str) -> str | None:
        """Append a failure line to 99-System/Logs/YYYY-MM-DD.md. Never silent."""
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        ts = now.strftime("%H:%M")
        path = f"{SYSTEM_LOG_DIR}/{today}.md"
        line = f"- {ts} {detail}\n"
        try:
            try:
                await self._backend.append(path, line)
            except Exception:
                await self._backend.put(path, f"# {today}\n\n{line}")
            return path
        except Exception as exc:
            logger.warning("Vault failure log write failed: {}", type(exc).__name__)
            return None

    async def _daily_template_body(self, today: str, created: str) -> str:
        try:
            raw = await self._backend.get(DAILY_TEMPLATE_PATH)
            rendered = _render_daily_template(raw, today, created)
            if "## Log" in rendered:
                return rendered
        except Exception:
            logger.debug("Daily template missing or unreadable; using built-in")
        return _builtin_daily_note(today, created)

    async def _read_or_create_daily(self, path: str, today: str, created: str) -> str:
        try:
            return await self._backend.get(path)
        except Exception:
            body = await self._daily_template_body(today, created)
            _assert_writable(path)
            await self._backend.put(path, body)
            logger.info("Obsidian create {}", path)
            return body

    async def append_to_inbox(
        self,
        message: str,
        source: str = "user",
        tag: str = "inbox",
    ) -> str:
        """Append one capture under ## Log in 00-Inbox/Daily/YYYY-MM-DD.md.

        Five types only (food, finance, idea, task, exercise). Unparseable
        input is written verbatim to 00-Inbox/Unsorted/. Failures log to
        99-System/Logs/. Never writes 01–05, Career/Profile, or Context.
        Existing daily-note lines are never edited or deleted.
        """
        del tag  # v1 uses [src::], not #inbox
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        created = now.strftime("%Y-%m-%dT%H:%M")
        stamp = now.strftime("%Y-%m-%d-%H%M%S")
        raw = (message or "").strip() or "(empty capture)"
        src = _src_value(source)
        try:
            cleaned = _strip_capture_prefix(raw)
            typ = classify_log_type(cleaned)
            if typ is None:
                path = f"{UNSORTED_DIR}/{stamp}.md"
                body = (
                    f"---\n"
                    f"type: unsorted\n"
                    f"created: {created}\n"
                    f"src: {src}\n"
                    f"---\n\n"
                    f"{raw}\n"
                )
                await self.create_note(path, body)
                return path

            daily_path = f"{DAILY_NOTE_DIR}/{today}.md"
            entry = _format_log_entry(cleaned, typ, src)
            existing = await self._read_or_create_daily(daily_path, today, created)
            updated = _insert_under_heading(existing, "## Log", entry)
            if not _lines_preserved(existing, updated):
                raise RuntimeError("refusing daily write: existing lines would change")
            _assert_writable(daily_path)
            await self._backend.put(daily_path, updated)
            logger.info("Obsidian capture → {}", daily_path)
            return daily_path
        except PermissionError:
            raise
        except Exception as exc:
            logger.warning("append_to_inbox failed: {}", type(exc).__name__)
            await self._log_system_failure(f"append_to_inbox failed: {type(exc).__name__}")
            raise
