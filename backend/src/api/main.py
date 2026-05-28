"""FastAPI app.

Endpoints:
  POST /api/chat                   — send a message, stream agent response via SSE
  POST /api/upload                 — upload a file (receipt etc.), returns file_id
  GET  /api/health                 — liveness
  GET  /api/reading-list           — list active reading list items + stats
  GET  /api/reading-list/stats     — stats only
  PATCH /api/reading-list/{id}     — update status / progress
  DELETE /api/reading-list/{id}    — hard delete + remove mirror
  POST /api/jobs/morning-brief     — manually trigger the morning brief
  GET  /api/jobs/knowledge-brief   — alias kept for backward compat
  GET  /api/morning-brief/latest   — fetch today's brief markdown + date
  GET  /api/plaid/link-token       — create a Plaid Link token for frontend
  POST /api/plaid/exchange         — exchange Plaid public_token for access_token

Run:
  uv run python -m src.api.main
"""
from __future__ import annotations

import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel
from sqlmodel import Session
from sse_starlette.sse import EventSourceResponse

from src.agents.knowledge import build_morning_brief
from src.config import get_settings
from src.orchestrator import handle_message
from src.scheduler import start_scheduler, stop_scheduler
from src.services import reading_list as rl
from src.storage import get_session, init_db
from src.storage.models import ItemStatus


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

# CORS: allow localhost, 127.0.0.1, and any Tailscale MagicDNS hostname on port 5173.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*):5173",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upload directory
UPLOAD_DIR = Path(settings.data_dir) / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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


class ReadingListPatch(BaseModel):
    status: str | None = None
    progress: int | None = None


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat", dependencies=[Depends(require_token)])
async def chat(req: ChatRequest):
    """Send a message, get a streaming response via SSE."""
    async def stream():
        try:
            yield {"event": "status", "data": "thinking"}
            result = await handle_message(req.message, req.attachments)
            yield {"event": "message", "data": result.get("reply", "")}
            if result.get("obsidian_path"):
                yield {"event": "obsidian", "data": result["obsidian_path"]}
            yield {"event": "intent", "data": result.get("intent", "general")}
            yield {"event": "done", "data": "1"}
        except Exception as e:
            logger.exception("chat error")
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(stream())


@app.post("/api/upload", dependencies=[Depends(require_token)])
async def upload(file: UploadFile = File(...)) -> dict:  # noqa: B008
    file_id = str(uuid.uuid4())
    suffix = Path(file.filename or "").suffix
    dest = UPLOAD_DIR / f"{file_id}{suffix}"
    content = await file.read()
    dest.write_bytes(content)
    logger.info("Uploaded {} -> {} ({} bytes)", file.filename, dest, len(content))
    return {
        "file_id": file_id,
        "path": str(dest),
        "size": len(content),
        "media_type": file.content_type,
    }


# ── Reading list endpoints ─────────────────────────────────────────────────────

def _item_to_dict(item) -> dict:
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


@app.get("/api/reading-list/stats", dependencies=[Depends(require_token)])
async def get_reading_list_stats(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return rl.stats(session)


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


# ── Morning brief endpoints ────────────────────────────────────────────────────

@app.post("/api/jobs/morning-brief", dependencies=[Depends(require_token)])
async def run_morning_brief_job() -> dict:
    """Manual trigger for the daily morning brief."""
    path = await build_morning_brief()
    return {"ok": True, "path": path}


# Backward-compat alias
@app.post("/api/jobs/knowledge-brief", dependencies=[Depends(require_token)])
async def run_knowledge_brief_job() -> dict:
    path = await build_morning_brief()
    return {"ok": True, "path": path}


@app.get("/api/morning-brief/latest", dependencies=[Depends(require_token)])
async def get_latest_morning_brief() -> dict:
    """Return today's morning brief markdown + date (for the frontend banner)."""
    from src.integrations import ObsidianClient

    today = __import__("datetime").date.today().isoformat()
    path = f"00-Inbox/Daily/{today}-Ross.md"
    try:
        async with ObsidianClient() as obs:
            content = await obs.get_note(path)
        return {"date": today, "path": path, "content": content}
    except Exception:
        return {"date": today, "path": None, "content": None}


# ── Plaid endpoints ────────────────────────────────────────────────────────────

@app.get("/api/plaid/link-token", dependencies=[Depends(require_token)])
async def plaid_link_token() -> dict:
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
async def plaid_exchange(req: PlaidExchangeRequest) -> dict:
    try:
        from src.integrations.plaid_client import PlaidClient
        client = PlaidClient()
        access = await client.exchange_public_token(req.public_token)
        logger.info("Plaid link complete (token prefix: {}...)", access[:8])
        return {"ok": True}
    except Exception as e:
        logger.exception("plaid exchange failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


def main() -> None:
    import uvicorn

    logger.info("Starting Second Brain API on http://{}:{}", settings.app_host, settings.app_port)
    uvicorn.run(
        "src.api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.environment == "development",
        reload_dirs=["src"],
    )


if __name__ == "__main__":
    main()
