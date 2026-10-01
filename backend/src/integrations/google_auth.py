"""Shared Google OAuth credentials for Calendar, Gmail, and People.

Supports two storage backends (tried in order):
1. Database (UserConfig key=google_token_json) — used on Render / cloud.
2. File (settings.google_token_path) — used locally on Mac.
"""
from __future__ import annotations

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from loguru import logger

from src.config import get_settings

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]

_DB_KEY = "google_token_json"


def _save_to_db(creds: Credentials) -> None:
    """Persist refreshed token back to the database."""
    try:
        from sqlmodel import Session, select

        from src.storage import _get_engine
        from src.storage.models import UserConfig

        with Session(_get_engine()) as session:
            row = session.exec(
                select(UserConfig).where(UserConfig.key == _DB_KEY)
            ).first()
            if row:
                row.value = creds.to_json()
                session.add(row)
            else:
                session.add(UserConfig(key=_DB_KEY, value=creds.to_json()))
            session.commit()
    except Exception as exc:
        logger.warning("Could not save Google token to DB: {}", exc)


def load_google_credentials() -> Credentials | None:
    """Load credentials — from DB first, then from file."""
    settings = get_settings()

    # 1. Try database
    try:
        from sqlmodel import Session, select

        from src.storage import _get_engine
        from src.storage.models import UserConfig

        with Session(_get_engine()) as session:
            row = session.exec(
                select(UserConfig).where(UserConfig.key == _DB_KEY)
            ).first()
            if row:
                creds = Credentials.from_authorized_user_info(
                    json.loads(row.value), GOOGLE_SCOPES
                )
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    _save_to_db(creds)
                return creds
    except Exception as exc:
        logger.debug("DB Google token not available: {}", exc)

    # 2. Fall back to file (local Mac dev)
    if not settings.google_token_path:
        return None
    token_path = Path(settings.google_token_path)
    if not token_path.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(token_path), GOOGLE_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
    return creds


def build_oauth_flow(redirect_uri: str) -> Flow:
    """Build a web-redirect OAuth flow (used by /api/auth/google/start)."""
    settings = get_settings()
    if not settings.google_oauth_client_secrets:
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_SECRETS not set")

    secrets_path = Path(settings.google_oauth_client_secrets)
    if not secrets_path.exists():
        raise FileNotFoundError(f"Missing {secrets_path}")

    flow = Flow.from_client_secrets_file(
        str(secrets_path),
        scopes=GOOGLE_SCOPES,
        redirect_uri=redirect_uri,
    )
    return flow


def run_google_oauth_flow() -> None:
    """One-time interactive OAuth setup for local Mac dev."""
    settings = get_settings()
    if not settings.google_oauth_client_secrets:
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_SECRETS not set in .env")

    secrets_path = Path(settings.google_oauth_client_secrets)
    if not secrets_path.exists():
        raise FileNotFoundError(
            f"Missing {secrets_path}. Download OAuth client JSON from Google Cloud Console."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), GOOGLE_SCOPES)
    creds = flow.run_local_server(port=0)

    # Save to both file and DB
    token_path = Path(settings.google_token_path or "./secrets/google_token.json")
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    _save_to_db(creds)
    logger.info("Google OAuth token saved to {} and DB", token_path)
