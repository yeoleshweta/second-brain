"""Persist readable content (markdown + PDF) for reading-list items."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import httpx
from loguru import logger

from src.config import get_settings

ARXIV_ABS_RE = re.compile(r"arxiv\.org/abs/([\d.]+(?:v\d+)?)", re.IGNORECASE)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
}


def _data_dir() -> Path:
    settings = get_settings()
    return Path(settings.data_dir)


def item_content_dir(item_id: int) -> Path:
    path = _data_dir() / "reading" / str(item_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_content_path(relative: str | None) -> Path | None:
    if not relative:
        return None
    path = _data_dir() / relative
    return path if path.exists() else None


def write_markdown(item_id: int, body: str) -> str:
    dest = item_content_dir(item_id) / "content.md"
    dest.write_text(body.strip() + "\n", encoding="utf-8")
    return str(dest.relative_to(_data_dir()))


def copy_pdf(item_id: int, src: Path) -> str:
    dest = item_content_dir(item_id) / "document.pdf"
    shutil.copy2(src, dest)
    return str(dest.relative_to(_data_dir()))


def copy_document(item_id: int, src: Path) -> str:
    """Copy an uploaded document preserving its extension."""
    suffix = src.suffix.lower() or ".bin"
    dest = item_content_dir(item_id) / f"document{suffix}"
    shutil.copy2(src, dest)
    return str(dest.relative_to(_data_dir()))


def resolve_pdf_url(url: str) -> str:
    m = ARXIV_ABS_RE.search(url)
    if m:
        return f"https://arxiv.org/pdf/{m.group(1)}.pdf"
    if url.lower().endswith(".pdf"):
        return url
    return url


def is_probable_pdf_url(url: str) -> bool:
    lower = url.lower()
    if lower.endswith(".pdf"):
        return True
    if ARXIV_ABS_RE.search(url):
        return True
    if "/pdf/" in lower or "filetype=pdf" in lower:
        return True
    return False


def _is_pdf_bytes(data: bytes) -> bool:
    return len(data) >= 4 and data[:4] == b"%PDF"


async def download_pdf(item_id: int, url: str) -> str | None:
    pdf_url = resolve_pdf_url(url)
    dest = item_content_dir(item_id) / "document.pdf"
    try:
        async with httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers=_BROWSER_HEADERS,
        ) as client:
            resp = await client.get(pdf_url)
            resp.raise_for_status()
            content_type = (resp.headers.get("content-type") or "").lower()
            body = resp.content
            if "pdf" not in content_type and not pdf_url.lower().endswith(".pdf"):
                if not _is_pdf_bytes(body):
                    logger.warning("URL did not return PDF content: {}", pdf_url)
                    return None
            if not _is_pdf_bytes(body):
                logger.warning("Downloaded body is not a PDF: {}", pdf_url)
                return None
            dest.write_bytes(body)
    except Exception as exc:
        logger.warning("PDF download failed for {}: {}", pdf_url, exc)
        return None
    return str(dest.relative_to(_data_dir()))


MAX_BOOK_TEXT_CHARS = 500_000


async def save_gutenberg_book(
    item_id: int,
    *,
    title: str,
    author_line: str,
    formats: dict[str, str],
    canonical_url: str,
) -> tuple[str | None, str]:
    """Download a Gutenberg book. Returns (content_path, format_label)."""
    from src.integrations.gutenberg import pick_read_format

    picked = pick_read_format(formats)
    if not picked:
        return None, "none"

    mime_key, download_url = picked
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(download_url)
            resp.raise_for_status()
            raw = resp.content
    except Exception as exc:
        logger.warning("Gutenberg download failed for {}: {}", download_url, exc)
        return None, "failed"

    header = f"# {title}\n\n*{author_line} · [Project Gutenberg]({canonical_url})*\n\n---\n\n"

    if "text/plain" in mime_key:
        text = raw.decode("utf-8", errors="replace")[:MAX_BOOK_TEXT_CHARS]
        rel = write_markdown(item_id, header + text)
        return rel, "text"

    if "pdf" in mime_key:
        dest = item_content_dir(item_id) / "document.pdf"
        dest.write_bytes(raw)
        return str(dest.relative_to(_data_dir())), "pdf"

    if "epub" in mime_key:
        dest = item_content_dir(item_id) / "document.epub"
        dest.write_bytes(raw)
        summary_path = item_content_dir(item_id) / "content.md"
        summary_path.write_text(
            header + "_Full EPUB downloaded — open from your reading list file storage._\n",
            encoding="utf-8",
        )
        return str(summary_path.relative_to(_data_dir())), "epub"

    dest = item_content_dir(item_id) / "document.bin"
    dest.write_bytes(raw)
    fallback = header + "_Downloaded — format not fully supported in-app._"
    return str(write_markdown(item_id, fallback)), "other"


def read_markdown(relative: str | None) -> str | None:
    path = resolve_content_path(relative)
    if not path or path.suffix != ".md":
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not read markdown at {}: {}", relative, exc)
        return None


def read_text_file(relative: str | None) -> str | None:
    path = resolve_content_path(relative)
    if not path or path.suffix.lower() not in {".txt", ".md", ".markdown"}:
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.warning("Could not read text at {}: {}", relative, exc)
        return None


def read_pdf_bytes(relative: str | None) -> bytes | None:
    path = resolve_content_path(relative)
    if not path or path.suffix.lower() != ".pdf":
        return None
    try:
        return path.read_bytes()
    except Exception as exc:
        logger.warning("Could not read PDF at {}: {}", relative, exc)
        return None


def delete_item_content(item_id: int) -> None:
    path = _data_dir() / "reading" / str(item_id)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def is_jina_pdf_placeholder(text: str) -> bool:
    """Jina returns metadata instead of PDF bytes for direct .pdf URLs."""
    lower = text.lower()
    return (
        "iframe that are currently hidden" in lower
        or "consider enabling iframe processing" in lower
        or ("url source:" in lower and "markdown content:" in lower)
    )


def _markdown_is_stale_pdf_scrape(item) -> bool:
    from src.storage.models import ReadingListItem

    if not isinstance(item, ReadingListItem) or not item.url:
        return False
    if not is_probable_pdf_url(item.url):
        return False
    if item.content_path and item.content_path.endswith(".pdf"):
        return False
    if not item.content_path:
        return True
    return item.content_path.endswith(".md")


def _wants_pdf_for_item(item, *, prefer_pdf: bool) -> bool:
    from src.storage.models import ItemKind, ReadingListItem

    if not isinstance(item, ReadingListItem) or not item.url:
        return False
    return (
        prefer_pdf
        or item.kind in {ItemKind.PDF, ItemKind.PAPER}
        or is_probable_pdf_url(item.url)
        or "arxiv.org" in item.url
    )


async def ensure_item_content(
    session,
    item,
    *,
    prefer_pdf: bool = False,
) -> object:
    """Lazy-fetch readable content for legacy items missing content_path."""
    from src.storage.models import ReadingListItem

    if not isinstance(item, ReadingListItem) or item.id is None:
        return item

    stale_pdf = _markdown_is_stale_pdf_scrape(item)
    if item.content_path and resolve_content_path(item.content_path) and not stale_pdf:
        return item

    if stale_pdf and item.content_path:
        stale_path = resolve_content_path(item.content_path)
        if stale_path and stale_path.exists():
            stale_path.unlink()
        item.content_path = None

    from src.storage.models import ItemKind

    if item.url:
        if _wants_pdf_for_item(item, prefer_pdf=prefer_pdf):
            path = await download_pdf(item.id, item.url)
            if path:
                item.content_path = path
                item.kind = ItemKind.PDF

        if not item.content_path and not is_probable_pdf_url(item.url):
            from src.agents.knowledge import _looks_like_failed_fetch, fetch_url_text

            try:
                text = await fetch_url_text(item.url)
                if _looks_like_failed_fetch(item.title, text):
                    logger.warning("Lazy fetch got error page for item {}", item.id)
                elif is_jina_pdf_placeholder(text):
                    logger.warning("Skipping Jina PDF placeholder for item {}", item.id)
                else:
                    md = f"# {item.title}\n\nSource: {item.url}\n\n---\n\n{text}"
                    item.content_path = write_markdown(item.id, md)
            except Exception as exc:
                logger.warning("Lazy content fetch failed for item {}: {}", item.id, exc)
    elif item.summary:
        item.content_path = write_markdown(
            item.id,
            f"# {item.title}\n\n{item.summary}",
        )

    if item.content_path:
        session.add(item)
        session.commit()
        session.refresh(item)
    return item
