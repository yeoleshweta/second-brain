"""Shared Google OAuth credentials for Calendar, Gmail, and People."""
from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from loguru import logger

from src.config import get_settings

# Re-run `uv run python -m src.integrations.google_calendar auth` after adding scopes.
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def load_google_credentials() -> Credentials | None:
    settings = get_settings()
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


def run_google_oauth_flow() -> None:
    """One-time interactive OAuth setup. Call from a command line."""
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
    token_path = Path(settings.google_token_path or "./secrets/google_token.json")
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    logger.info("Google OAuth token saved to {}", token_path)
