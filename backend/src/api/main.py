"""FastAPI app.

Endpoints:
  POST /api/chat            — send a message, stream agent response via SSE
  POST /api/upload          — upload a file (receipt etc.), returns file_id
  GET  /api/plaid/link-token — create a Plaid Link token for frontend
  POST /api/plaid/exchange  — exchange Plaid public_token for access_token
  GET  /api/health          — liveness

Run:
  uv run python -m src.api.main
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.config import get_settings
from src.orchestrator import handle_message


def _setup_logging() -> None:
    settings = get_settings()
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)
    Path("logs").mkdir(exist_ok=True)
    logger.add("logs/app.log", rotation="10 MB", retention="30 days", level="DEBUG")


_setup_logging()
settings = get_settings()

app = FastAPI(title="Second Brain API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upload directory
UPLOAD_DIR = Path(settings.data_dir) / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── Auth: simple shared-token because the app is single-user, local-only ──
def require_token(authorization: Annotated[str | None, Header()] = None) -> None:
    if settings.environment == "development" and not settings.app_api_token:
        return  # dev convenience
    expected = f"Bearer {settings.app_api_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="invalid token")


# ── Models ────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    attachments: list[dict] = []


# ── Routes ────────────────────────────────────────────────────────────


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat", dependencies=[Depends(require_token)])
async def chat(req: ChatRequest):
    """Send a message, get a streaming response.

    The current orchestrator returns a single reply; we wrap it in SSE so the
    frontend is ready when we add token streaming later.
    """
    async def stream():
        try:
            yield {"event": "status", "data": "thinking"}
            result = await handle_message(req.message, req.attachments)

            # Could chunk this in future; for now send the whole reply
            yield {
                "event": "message",
                "data": result.get("reply", ""),
            }
            if result.get("obsidian_path"):
                yield {
                    "event": "obsidian",
                    "data": result["obsidian_path"],
                }
            yield {
                "event": "intent",
                "data": result.get("intent", "general"),
            }
            yield {"event": "done", "data": "1"}
        except Exception as e:
            logger.exception("chat error")
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(stream())


@app.post("/api/upload", dependencies=[Depends(require_token)])
async def upload(file: UploadFile = File(...)) -> dict:
    """Upload an image or document. Returns a file_id you can reference in /chat."""
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


# ── Plaid endpoints ──────────────────────────────────────────────────


@app.get("/api/plaid/link-token", dependencies=[Depends(require_token)])
async def plaid_link_token() -> dict:
    """Create a Plaid Link token for the frontend to open the Link UI."""
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
    """Exchange public_token (from frontend Plaid Link) for a long-lived access_token.

    TODO: encrypt and store access_token in SQLite. For now we just return ok.
    """
    try:
        from src.integrations.plaid_client import PlaidClient

        client = PlaidClient()
        access = await client.exchange_public_token(req.public_token)
        # TODO: store access encrypted
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
        reload_excludes=[".venv", "logs", "data", "__pycache__"],
    )


if __name__ == "__main__":
    main()
