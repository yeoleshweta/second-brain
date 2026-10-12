"""Save one Instagram or LinkedIn link the user shared from their phone.

Does not log into those apps or fetch the page. The Shortcuts share sheet
sends the link, and this stores that link.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TRAIL = ".,);]>"
_HOSTS = ("instagram.com", "instagr.am", "linkedin.com", "lnkd.in")
_MAX_NOTE = 280


class ShareRejectedError(ValueError):
    """The share did not contain an Instagram or LinkedIn link."""


def _clean_url(raw: str) -> str:
    return raw.strip().rstrip(_TRAIL)


def _allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return False
    return any(host == name or host.endswith(f".{name}") for name in _HOSTS)


def _label(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "linkedin.com" in host or host.endswith("lnkd.in"):
        return "LinkedIn"
    return "Instagram"


def parse_share(url: str = "", text: str = "") -> tuple[str, str, str]:
    """Return the link, Instagram or LinkedIn, and a short note."""
    blob = f"{url}\n{text}"
    found = [_clean_url(match) for match in _URL_RE.findall(blob)]
    link = next((item for item in found if _allowed(item)), "")
    if not link:
        raise ShareRejectedError("Share an Instagram or LinkedIn link.")
    note = text
    for item in found:
        note = note.replace(item, " ")
    note = re.sub(r"\s+", " ", note).strip(" -–—")
    if len(note) > _MAX_NOTE:
        note = note[: _MAX_NOTE - 1].rstrip() + "…"
    return link, _label(link), note


def share_line(link: str, label: str, note: str) -> str:
    line = f"Shared from {label}: {link}"
    if note:
        line = f"{line} — {note}"
    return line
