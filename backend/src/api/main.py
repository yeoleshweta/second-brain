"""FastAPI app.

Endpoints:
  POST /api/chat                   — send a message, stream agent response via SSE
  POST /api/upload                 — upload a file (receipt etc.), returns file_id
  GET  /api/health                 — liveness
  GET  /api/reading-list           — list active reading list items + stats
  GET  /api/reading-list/stats     — stats only
  PATCH /api/reading-list/{id}     — update status / progress
  DELETE /api/reading-list/{id}    — hard delete + remove mirror
  GET  /api/reading-list/{id}/content — markdown body or PDF metadata for in-app reader
  GET  /api/reading-list/{id}/file    — stream stored PDF
  POST /api/jobs/morning-brief     — manually trigger the morning brief
  GET  /api/jobs/knowledge-brief   — alias kept for backward compat
  GET  /api/morning-brief/latest   — fetch today's brief markdown + date
  GET  /api/plaid/link-token       — create a Plaid Link token for frontend
  POST /api/plaid/exchange         — exchange Plaid public_token, store encrypted token
  GET  /api/plaid/status           — linked banks + config readiness
  DELETE /api/plaid/items/{item_id} — unlink a bank (Plaid + local DB)

Run:
  uv run python -m src.api.main
"""
from __future__ import annotations

import re
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel
from sqlmodel import Session
from sse_starlette.sse import EventSourceResponse

from src.agents.knowledge import build_morning_brief
from src.config import get_settings
from src.integrations.google_calendar import google_calendar_status
from src.orchestrator import handle_message
from src.scheduler import start_scheduler, stop_scheduler
from src.services import chat_history as chat_store
from src.services import reading_list as rl
from src.services import usage as usage_service
from src.services import user_config
from src.storage import ReadingListItem, get_session, init_db
from src.storage.models import ItemKind, ItemStatus


def _setup_logging() -> None:
    settings = get_settings()
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)
    Path("logs").mkdir(exist_ok=True)
    logger.add("logs/app.log", rotation="10 MB", retention="30 days", level="DEBUG")


_setup_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="Second Brain API", lifespan=lifespan)

# CORS: allow:
#   • localhost dev (Vite)
#   • Tailscale MagicDNS hostnames on port 5173
#   • Capacitor native apps (capacitor://localhost, ionic://localhost)
#   • Any configured FRONTEND_ORIGIN (for Railway / cloud deploys)
_EXTRA_ORIGINS = [o.strip() for o in settings.frontend_origin.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "capacitor://localhost",   # iOS Capacitor native
        "ionic://localhost",       # Android Capacitor
        "http://localhost",        # Android emulator
        *_EXTRA_ORIGINS,
    ],
    allow_origin_regex=(
        # localhost dev + Tailscale + Vercel preview/prod URLs
        r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
        r"|https://[a-zA-Z0-9-]+(\.vercel\.app)"
        r"|https://[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*"  # any configured custom domain
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upload directory
UPLOAD_DIR = Path(settings.data_dir) / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_UPLOAD_TYPE_BY_EXT = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".rtf": "application/rtf",
    ".csv": "text/csv",
}


def _guess_upload_media_type(filename: str | None, content_type: str | None) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in _UPLOAD_TYPE_BY_EXT:
        return _UPLOAD_TYPE_BY_EXT[ext]
    if content_type and content_type != "application/octet-stream":
        return content_type
    return content_type or "application/octet-stream"


# ── Auth ───────────────────────────────────────────────────────────────────────

def require_token(authorization: Annotated[str | None, Header()] = None) -> None:
    if settings.environment == "development" and not settings.app_api_token:
        return
    expected = f"Bearer {settings.app_api_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="invalid token")


# ── Pydantic models ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    attachments: list[dict] = []
    chat_history: list[dict] = []
    session_id: str | None = None


class ReadingListAddRequest(BaseModel):
    url: str | None = None
    title: str
    summary: str | None = None
    source: str | None = None
    kind: str = "url"
    tags: str = ""
    pdf_url: str | None = None


class AddSuggestionsRequest(BaseModel):
    items: list[ReadingListAddRequest]
    fetch_content: bool = True


class ReadingListPatch(BaseModel):
    status: str | None = None
    progress: int | None = None


class UserSettingsPatch(BaseModel):
    daily_reading_minutes_goal: int | None = None
    daily_practice_minutes_goal: int | None = None
    active_skills: list[str] | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    nudge_morning_brief: bool | None = None
    nudge_mid_day_reading: bool | None = None
    nudge_evening_reading: bool | None = None
    nudge_evening_practice: bool | None = None
    nudge_weekly_review: bool | None = None
    nudge_discovery: bool | None = None


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/chat/sessions", dependencies=[Depends(require_token)])
async def list_chat_sessions(
    session: Annotated[Session, Depends(get_session)],
    limit: int = 30,
) -> dict:
    rows = chat_store.list_sessions(session, limit=min(limit, 100))
    out = []
    for row in rows:
        msgs = chat_store.list_messages(session, row.id)
        out.append(chat_store.session_to_api(row, message_count=len(msgs)))
    return {"sessions": out}


@app.post("/api/chat/sessions", dependencies=[Depends(require_token)])
async def create_chat_session(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    row = chat_store.create_session(session)
    return chat_store.session_to_api(row)


@app.get("/api/chat/sessions/{session_id}/messages", dependencies=[Depends(require_token)])
async def get_chat_session_messages(
    session_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    row = chat_store.get_session(session, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="session not found")
    msgs = chat_store.list_messages(session, session_id)
    return {
        "session": chat_store.session_to_api(row, message_count=len(msgs)),
        "messages": [chat_store.message_to_api(m) for m in msgs],
    }


@app.post("/api/chat", dependencies=[Depends(require_token)])
async def chat(req: ChatRequest, db: Annotated[Session, Depends(get_session)]):
    """Send a message, get a streaming response via SSE."""
    async def stream():
        try:
            chat_session = (
                chat_store.get_session(db, req.session_id)
                if req.session_id
                else None
            )
            if not chat_session:
                chat_session = chat_store.create_session(
                    db,
                    title=chat_store.title_from_message(req.message),
                )

            session_id = chat_session.id
            yield {"event": "session_id", "data": session_id}

            db_history = chat_store.recent_history(db, session_id, limit=20)
            history = db_history if db_history else req.chat_history

            chat_store.append_message(
                db,
                session_id,
                role="user",
                content=req.message,
            )
            chat_store.maybe_set_title_from_first_message(db, chat_session, req.message)

            yield {"event": "status", "data": "thinking"}
            result = await handle_message(
                req.message,
                req.attachments,
                history,
                session_id=session_id,
            )

            reply = result.get("reply", "")
            intent = result.get("intent")
            extra: dict = {}
            if result.get("digest_items"):
                extra["digestItems"] = result["digest_items"]
            if result.get("suggest_items"):
                extra["suggestItems"] = result["suggest_items"]
            if result.get("book_items"):
                extra["bookItems"] = result["book_items"]
            if result.get("obsidian_path"):
                extra["obsidianPath"] = result["obsidian_path"]

            chat_store.append_message(
                db,
                session_id,
                role="assistant",
                content=reply,
                intent=intent,
                extra=extra or None,
            )

            yield {"event": "message", "data": reply}
            if result.get("digest_items"):
                import json as _json
                yield {"event": "digest_items", "data": _json.dumps(result["digest_items"])}
            if result.get("suggest_items"):
                import json as _json
                yield {"event": "suggest_items", "data": _json.dumps(result["suggest_items"])}
            if result.get("book_items"):
                import json as _json
                yield {"event": "book_items", "data": _json.dumps(result["book_items"])}
            if result.get("obsidian_path"):
                yield {"event": "obsidian", "data": result["obsidian_path"]}
            yield {"event": "intent", "data": intent or "general"}
            yield {"event": "done", "data": "1"}
        except Exception as e:
            logger.exception("chat error")
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(stream())


MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


@app.post("/api/upload", dependencies=[Depends(require_token)])
async def upload(file: UploadFile = File(...)) -> dict:  # noqa: B008
    file_id = str(uuid.uuid4())
    suffix = Path(file.filename or "").suffix
    dest = UPLOAD_DIR / f"{file_id}{suffix}"
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )
    dest.write_bytes(content)
    media_type = _guess_upload_media_type(file.filename, file.content_type)
    logger.info("Uploaded {} -> {} ({} bytes)", file.filename, dest, len(content))
    return {
        "file_id": file_id,
        "path": str(dest),
        "size": len(content),
        "media_type": media_type,
        "filename": file.filename or f"upload{suffix}",
    }


# ── Reading list endpoints ─────────────────────────────────────────────────────

def _item_to_dict(item) -> dict:
    content_format: str | None = None
    if item.content_path:
        content_format = "pdf" if item.content_path.endswith(".pdf") else "markdown"
    return {
        "id": item.id,
        "url": item.url,
        "title": item.title,
        "summary": item.summary,
        "source": item.source,
        "kind": item.kind,
        "tags": item.tags,
        "status": item.status,
        "progress": item.progress,
        "saved_at": item.saved_at.isoformat(),
        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
        "mirror_path": item.mirror_path,
        "content_path": item.content_path,
        "has_content": bool(item.content_path),
        "content_format": content_format,
    }


@app.get("/api/reading-list", dependencies=[Depends(require_token)])
async def get_reading_list(
    session: Annotated[Session, Depends(get_session)],
    status: str = "unread,in_progress",
) -> dict:
    wanted = {s.strip() for s in status.split(",")}
    all_items = rl.list_all(session)
    items = [i for i in all_items if i.status in wanted]
    return {
        "items": [_item_to_dict(i) for i in items],
        "stats": rl.stats(session),
    }


@app.post("/api/reading-list", dependencies=[Depends(require_token)])
async def add_reading_list_item(
    body: ReadingListAddRequest,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    """Directly add an item (e.g., from the digest UI) without going through chat."""
    from src.agents.knowledge import _write_mirror
    from src.integrations import ObsidianClient

    kind = ItemKind(body.kind) if body.kind in {k.value for k in ItemKind} else ItemKind.URL
    item = rl.add(
        session,
        url=body.url or None,
        title=body.title,
        summary=body.summary,
        source=body.source,
        kind=kind,
        tags=body.tags,
    )
    if item is None:
        # Dedup — return existing item
        from sqlmodel import select as _select
        existing = session.exec(
            _select(ReadingListItem).where(ReadingListItem.url == body.url)
        ).first()
        return {
            "saved": False,
            "duplicate": True,
            "item": _item_to_dict(existing) if existing else None,
        }

    try:
        async with ObsidianClient() as obs:
            mirror_path = await _write_mirror(item, obs)
        item.mirror_path = mirror_path
        session.add(item)
        session.commit()
        session.refresh(item)
    except Exception as e:
        logger.warning("Digest save mirror write failed: {}", e)

    return {"saved": True, "duplicate": False, "item": _item_to_dict(item)}


@app.post("/api/reading-list/add-suggestions", dependencies=[Depends(require_token)])
async def add_suggestions_to_reading_list(
    body: AddSuggestionsRequest,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    """Add one or more chat suggestions to the reading list with optional content fetch."""
    from src.agents.knowledge import _attach_readable_content, _write_mirror
    from src.integrations import ObsidianClient

    added: list[dict] = []
    duplicates: list[dict] = []

    for item_body in body.items:
        valid_kinds = {k.value for k in ItemKind}
        kind = ItemKind(item_body.kind) if item_body.kind in valid_kinds else ItemKind.URL
        item = rl.add(
            session,
            url=item_body.url or None,
            title=item_body.title,
            summary=item_body.summary,
            source=item_body.source,
            kind=kind,
            tags=item_body.tags,
        )
        if item is None:
            from sqlmodel import select as _select

            existing = None
            if item_body.url:
                existing = session.exec(
                    _select(ReadingListItem).where(ReadingListItem.url == item_body.url)
                ).first()
            dup_payload = (
                _item_to_dict(existing)
                if existing
                else {"title": item_body.title, "url": item_body.url}
            )
            duplicates.append(dup_payload)
            continue

        if body.fetch_content and item_body.url:
            from src.agents.knowledge import _should_save_as_pdf

            if _should_save_as_pdf(
                item_body.url,
                kind=item_body.kind,
                pdf_url=item_body.pdf_url,
            ):
                item, _ = await _attach_readable_content(
                    session,
                    item,
                    url=item_body.url,
                    pdf_url=item_body.pdf_url,
                    prefer_pdf=True,
                )

        try:
            async with ObsidianClient() as obs:
                mirror_path = await _write_mirror(item, obs)
            item.mirror_path = mirror_path
            session.add(item)
            session.commit()
            session.refresh(item)
        except Exception as e:
            logger.warning("Suggestion save mirror failed: {}", e)

        added.append(_item_to_dict(item))

    return {
        "added": len(added),
        "duplicate": len(duplicates),
        "items": added,
        "duplicates": duplicates,
    }


@app.post("/api/reading-list/gutenberg/{book_id}", dependencies=[Depends(require_token)])
async def download_gutenberg_book(
    book_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    """Download a Project Gutenberg book by Gutendex id (from chat book picker)."""
    from src.agents.knowledge import handle_download_gutenberg_id

    result = await handle_download_gutenberg_id(session, book_id)
    return result


@app.get("/api/reading-list/stats", dependencies=[Depends(require_token)])
async def get_reading_list_stats(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return rl.stats(session)


@app.get("/api/settings", dependencies=[Depends(require_token)])
async def get_settings_view(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return user_config.all_values(session)


@app.patch("/api/settings", dependencies=[Depends(require_token)])
async def patch_settings_view(
    body: UserSettingsPatch,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        if key == "active_skills":
            user_config.set_active_skills(session, list(value))
        elif isinstance(value, bool):
            user_config.set_value(session, key, "true" if value else "false")
        else:
            user_config.set_value(session, key, str(value))
    return user_config.all_values(session)


@app.get("/api/usage/today", dependencies=[Depends(require_token)])
async def usage_today(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return usage_service.today_summary(session)


@app.patch("/api/reading-list/{item_id}", dependencies=[Depends(require_token)])
async def patch_reading_list_item(
    item_id: int,
    body: ReadingListPatch,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    item = rl.find_by_id(session, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    from src.agents.knowledge import _move_to_archive, _rewrite_mirror_frontmatter
    from src.integrations import ObsidianClient

    if body.progress is not None:
        rl.update_progress(session, item, body.progress)
        try:
            async with ObsidianClient() as obs:
                await _rewrite_mirror_frontmatter(item, obs)
        except Exception as e:
            logger.warning("Mirror rewrite failed: {}", e)

    if body.status == ItemStatus.READ and item.status != ItemStatus.READ:
        rl.mark_read(session, item)
        try:
            async with ObsidianClient() as obs:
                new_path = await _move_to_archive(item, obs)
            if new_path:
                item.mirror_path = new_path
                session.add(item)
                session.commit()
        except Exception as e:
            logger.warning("Archive move failed: {}", e)

    session.refresh(item)
    return _item_to_dict(item)


@app.delete("/api/reading-list/{item_id}", dependencies=[Depends(require_token)])
async def delete_reading_list_item(
    item_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    item = rl.find_by_id(session, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    from src.agents.knowledge import _delete_mirror
    from src.integrations import ObsidianClient

    mirror = item.mirror_path
    rl.delete(session, item)
    if mirror:
        try:
            async with ObsidianClient() as obs:
                await _delete_mirror(mirror, obs)
        except Exception as e:
            logger.warning("Mirror delete failed: {}", e)

    return {"ok": True}


@app.get("/api/reading-list/{item_id}/content", dependencies=[Depends(require_token)])
async def get_reading_item_content(
    item_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    """Return readable content for in-app reader (markdown or PDF reference)."""
    from src.services import reading_content as rc

    item = rl.find_by_id(session, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item = await rc.ensure_item_content(
        session,
        item,
        prefer_pdf=bool(item.url and rc.is_probable_pdf_url(item.url)),
    )

    if item.content_path and item.content_path.endswith(".pdf"):
        return {
            "id": item.id,
            "title": item.title,
            "url": item.url,
            "format": "pdf",
            "summary": item.summary,
        }

    body = rc.read_markdown(item.content_path)
    if not body and item.summary:
        body = f"# {item.title}\n\n{item.summary}"
    if not body and item.url:
        body = f"# {item.title}\n\nNo cached content yet. [Open original]({item.url})"

    return {
        "id": item.id,
        "title": item.title,
        "url": item.url,
        "format": "markdown",
        "body": body or "",
        "summary": item.summary,
    }


@app.get("/api/reading-list/{item_id}/file", dependencies=[Depends(require_token)])
async def get_reading_item_file(
    item_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> FileResponse:
    """Stream stored PDF for an reading-list item."""
    from src.services import reading_content as rc

    item = rl.find_by_id(session, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item = await rc.ensure_item_content(session, item, prefer_pdf=True)
    path = rc.resolve_content_path(item.content_path)
    if not path or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="No PDF available for this item")

    safe_name = re.sub(r"[^\w\s-]", "", item.title).strip() or "document"
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{safe_name}.pdf",
    )


# ── Morning brief endpoints ────────────────────────────────────────────────────

@app.post("/api/jobs/morning-brief", dependencies=[Depends(require_token)])
async def run_morning_brief_job() -> dict:
    """Manual trigger for a Ross-only morning brief (backward compat)."""
    path = await build_morning_brief()
    return {"ok": True, "path": path}


# Backward-compat alias
@app.post("/api/jobs/knowledge-brief", dependencies=[Depends(require_token)])
async def run_knowledge_brief_job() -> dict:
    path = await build_morning_brief()
    return {"ok": True, "path": path}


@app.post("/api/jobs/combined-brief", dependencies=[Depends(require_token)])
async def run_combined_brief_job() -> dict:
    """Manual trigger for the unified Chandler + Ross morning brief."""
    from src.jobs.combined_brief import build_combined_brief
    path = await build_combined_brief()
    return {"ok": True, "path": path}


@app.post("/api/jobs/reachout", dependencies=[Depends(require_token)])
async def run_reachout_job() -> dict:
    """Manual trigger for Sunday reach-out section."""
    from src.jobs.reachout import append_reachout_to_brief
    await append_reachout_to_brief()
    return {"ok": True}


@app.get("/api/morning-brief/latest", dependencies=[Depends(require_token)])
async def get_latest_morning_brief() -> dict:
    """Return today's morning brief markdown + date (for the frontend banner).

    Prefers the combined brief (YYYY-MM-DD-Brief.md); falls back to Ross-only.
    """
    from src.integrations import ObsidianClient

    today = __import__("datetime").date.today().isoformat()
    for suffix in ("-Brief.md", "-Ross.md"):
        path = f"00-Inbox/Daily/{today}{suffix}"
        try:
            async with ObsidianClient() as obs:
                content = await obs.get_note(path)
            return {"date": today, "path": path, "content": content}
        except Exception:
            continue
    return {"date": today, "path": None, "content": None}


@app.get("/api/integrations/google/health", dependencies=[Depends(require_token)])
async def google_calendar_health() -> dict:
    """Check Google Calendar connectivity."""
    return google_calendar_status()


@app.get("/api/integrations/apple-books/health", dependencies=[Depends(require_token)])
async def apple_books_health() -> dict:
    """Check Apple Books MCP connectivity (macOS Books app)."""
    from src.integrations.apple_books import AppleBooksError, books_in_progress

    try:
        sample = await books_in_progress(limit=1)
        return {"connected": True, "sample": sample[:200] if sample else ""}
    except AppleBooksError as exc:
        return {"connected": False, "error": str(exc)}


@app.get("/api/chandler/agenda", dependencies=[Depends(require_token)])
async def get_chandler_agenda(scope: str = "today") -> dict:
    """Return today's or this week's agenda as structured JSON for the Agenda view."""
    from src.agents.calendar_agent import fetch_agenda

    if scope not in ("today", "week"):
        scope = "today"
    return await fetch_agenda(scope)


@app.get("/api/people", dependencies=[Depends(require_token)])
async def list_people() -> dict:
    """List all person notes (frontmatter only)."""
    from src.services import people
    all_p = people.list_all()
    return {
        "people": [
            {
                "filename": p["filename"],
                "frontmatter": p["frontmatter"],
                "body_preview": p["body_preview"],
            }
            for p in all_p
        ]
    }


# ── Plaid endpoints ────────────────────────────────────────────────────────────

def _plaid_configured() -> bool:
    s = get_settings()
    return bool(s.plaid_client_id and s.plaid_secret)


@app.get("/api/plaid/status", dependencies=[Depends(require_token)])
async def plaid_status(session: Annotated[Session, Depends(get_session)]) -> dict:
    from src.services import plaid_items as pi

    settings = get_settings()
    items = pi.list_items(session)
    return {
        "configured": _plaid_configured(),
        "encryption_configured": bool(settings.plaid_token_encryption_key),
        "linked": len(items) > 0,
        "env": settings.plaid_env,
        "items": [pi.item_summary(row) for row in items],
    }


@app.get("/api/plaid/link-token", dependencies=[Depends(require_token)])
async def plaid_link_token() -> dict:
    if not _plaid_configured():
        raise HTTPException(
            status_code=503,
            detail="Plaid is not configured — set PLAID_CLIENT_ID and PLAID_SECRET in .env",
        )
    try:
        from src.integrations.plaid_client import PlaidClient

        client = PlaidClient()
        token = await client.create_link_token(user_id="local-user")
        return {"link_token": token}
    except Exception as e:
        logger.exception("plaid link-token failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


class PlaidExchangeRequest(BaseModel):
    public_token: str


@app.post("/api/plaid/exchange", dependencies=[Depends(require_token)])
async def plaid_exchange(
    req: PlaidExchangeRequest,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    if not _plaid_configured():
        raise HTTPException(status_code=503, detail="Plaid is not configured")
    if not get_settings().plaid_token_encryption_key:
        raise HTTPException(
            status_code=503,
            detail="PLAID_TOKEN_ENCRYPTION_KEY not set — cannot store bank tokens securely",
        )
    try:
        from src.integrations.plaid_client import PlaidClient
        from src.services import plaid_items as pi

        client = PlaidClient()
        linked = await client.exchange_public_token(req.public_token)
        row = pi.upsert_item(
            session,
            item_id=linked["item_id"],
            institution_name=linked["institution_name"],
            access_token=linked["access_token"],
        )
        return {"ok": True, "item": pi.item_summary(row)}
    except Exception as e:
        logger.exception("plaid exchange failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/plaid/items/{item_id}", dependencies=[Depends(require_token)])
async def plaid_unlink_item(
    item_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    from src.integrations.plaid_client import PlaidClient
    from src.services import plaid_items as pi

    row = pi.get_by_item_id(session, item_id)
    if not row:
        raise HTTPException(status_code=404, detail="Bank link not found")

    try:
        access_token = pi.access_token_for_item(row)
        if _plaid_configured():
            client = PlaidClient()
            await client.remove_item(access_token)
    except Exception as e:
        logger.warning("Plaid item/remove failed for {}: {}", item_id, e)

    pi.delete_item(session, item_id)
    return {"ok": True}


# ── Apple Books sync endpoint ────────────────────────────────────────────────


class AppleBookPayload(BaseModel):
    apple_books_id: str
    title: str
    author: str
    genre: str | None = None
    progress: int = 0          # 0-100
    status: str = "unread"     # unread | reading | finished
    page_count: int | None = None
    rating: int | None = None
    last_opened_at: str | None = None
    finished_at: str | None = None
    purchased_at: str | None = None


class AppleBooksSyncRequest(BaseModel):
    books: list[AppleBookPayload]


@app.post("/api/reading/apple-books/sync", dependencies=[Depends(require_token)])
async def sync_apple_books(
    payload: AppleBooksSyncRequest,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    """Upsert Apple Books library data sent from the Mac sync script."""
    from datetime import datetime

    from sqlmodel import select

    from src.storage.models import ItemKind, ItemStatus

    _status_map = {
        "reading":  ItemStatus.IN_PROGRESS,
        "finished": ItemStatus.DONE,
        "unread":   ItemStatus.UNREAD,
    }

    added = updated = 0
    for book in payload.books:
        url = f"apple-books://{book.apple_books_id}"
        existing = session.exec(
            select(ReadingListItem).where(ReadingListItem.url == url)
        ).first()

        finished_dt: datetime | None = None
        if book.finished_at:
            try:
                finished_dt = datetime.fromisoformat(book.finished_at)
            except ValueError:
                pass

        tags = ",".join(filter(None, [book.genre, "apple-books"]))
        item_status = _status_map.get(book.status, ItemStatus.UNREAD)

        if existing:
            existing.title       = book.title
            existing.source      = book.author
            existing.progress    = book.progress
            existing.status      = item_status
            existing.tags        = tags
            existing.finished_at = finished_dt
            session.add(existing)
            updated += 1
        else:
            new_item = ReadingListItem(
                url         = url,
                title       = book.title,
                source      = book.author,
                kind        = ItemKind.BOOK,
                status      = item_status,
                progress    = book.progress,
                tags        = tags,
                finished_at = finished_dt,
            )
            session.add(new_item)
            added += 1

    session.commit()
    logger.info("Apple Books sync: {} added, {} updated", added, updated)
    return {"ok": True, "added": added, "updated": updated, "total": len(payload.books)}


@app.get("/api/reading/stats", dependencies=[Depends(require_token)])
async def reading_stats(session: Annotated[Session, Depends(get_session)]) -> dict:
    """Reading habit summary from synced Apple Books data."""
    from sqlmodel import select

    from src.storage.models import ItemStatus

    all_books = session.exec(
        select(ReadingListItem).where(ReadingListItem.tags.contains("apple-books"))  # type: ignore[arg-type]
    ).all()

    currently_reading = [b for b in all_books if b.status == ItemStatus.IN_PROGRESS]
    finished          = [b for b in all_books if b.status == ItemStatus.DONE]
    unread            = [b for b in all_books if b.status == ItemStatus.UNREAD]

    genres: dict[str, int] = {}
    for book in all_books:
        for tag in (book.tags or "").split(","):
            tag = tag.strip()
            if tag and tag != "apple-books":
                genres[tag] = genres.get(tag, 0) + 1

    return {
        "total":             len(all_books),
        "currently_reading": [{"title": b.title, "author": b.source, "progress": b.progress} for b in currently_reading],
        "finished_count":    len(finished),
        "unread_count":      len(unread),
        "top_genres":        sorted(genres.items(), key=lambda x: x[1], reverse=True)[:5],
        "recently_finished": [{"title": b.title, "author": b.source, "finished_at": b.finished_at.isoformat() if b.finished_at else None} for b in sorted(finished, key=lambda x: x.finished_at or datetime.min, reverse=True)[:5]],
    }


# ── Finance endpoints ───────────────────────────────────────────────────────────


@app.post("/api/finance/sync", dependencies=[Depends(require_token)])
async def finance_sync(session: Annotated[Session, Depends(get_session)]) -> dict:
    """Trigger a Plaid transaction sync for all linked items."""
    from src.services.plaid_sync import sync_all_items

    if not _plaid_configured():
        raise HTTPException(
            status_code=503,
            detail="Plaid not configured — set PLAID_CLIENT_ID and PLAID_SECRET",
        )
    results = await sync_all_items(session)
    return {"results": results}


@app.get("/api/finance/transactions", dependencies=[Depends(require_token)])
async def finance_transactions(
    session: Annotated[Session, Depends(get_session)],
    period: str = "month",
    limit: int = 50,
    merchant: str | None = None,
    category: str | None = None,
) -> dict:
    """List recent transactions with optional filters."""
    from src.services.transaction_queries import date_range_for_period, recent_transactions

    start, end = date_range_for_period(period)
    txs = recent_transactions(
        session,
        start=start,
        end=end,
        limit=limit,
        merchant_filter=merchant,
        category_filter=category,
    )
    return {"period": period, "count": len(txs), "transactions": txs}


@app.get("/api/finance/summary", dependencies=[Depends(require_token)])
async def finance_summary(
    session: Annotated[Session, Depends(get_session)],
    period: str = "month",
) -> dict:
    """Return spending summary: total, by-category breakdown, subscriptions."""
    from src.services.transaction_queries import (
        date_range_for_period,
        detect_subscriptions,
        spending_by_category,
        total_spent,
    )

    start, end = date_range_for_period(period)
    return {
        "period": period,
        "total": total_spent(session, start=start, end=end),
        "categories": spending_by_category(session, start=start, end=end, top_n=10),
        "subscriptions": detect_subscriptions(session),
    }


def main() -> None:
    import os

    import uvicorn

    # Render (and most cloud hosts) injects PORT at runtime. Fall back to settings.
    port = int(os.environ.get("PORT", settings.app_port))
    logger.info("Starting Second Brain API on http://{}:{}", settings.app_host, port)
    uvicorn.run(
        "src.api.main:app",
        host=settings.app_host,
        port=port,
        reload=settings.environment == "development",
        reload_dirs=["src"],
    )


if __name__ == "__main__":
    main()
