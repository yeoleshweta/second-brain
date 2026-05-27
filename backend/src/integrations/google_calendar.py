"""Google Calendar integration.

First-run flow:
  1. Create OAuth client in Google Cloud Console (Desktop app type).
  2. Download client_secret.json to backend/secrets/google_client_secret.json
  3. Run: uv run python -m src.integrations.google_calendar auth
     This opens a browser window to authorize and saves token to GOOGLE_TOKEN_PATH.

Scopes used: calendar (read + write events).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from loguru import logger

from src.config import get_settings

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/contacts.readonly",
]


def _load_credentials() -> Credentials | None:
    settings = get_settings()
    if not settings.google_token_path:
        return None
    token_path = Path(settings.google_token_path)
    if not token_path.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
    return creds


def run_oauth_flow() -> None:
    """One-time interactive OAuth setup. Call from a command line."""
    settings = get_settings()
    if not settings.google_oauth_client_secrets:
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_SECRETS not set in .env")

    secrets_path = Path(settings.google_oauth_client_secrets)
    if not secrets_path.exists():
        raise FileNotFoundError(
            f"Missing {secrets_path}. Download OAuth client JSON from Google Cloud Console."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path = Path(settings.google_token_path or "./secrets/google_token.json")
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    logger.info("Google OAuth token saved to {}", token_path)


class GoogleCalendarClient:
    def __init__(self) -> None:
        creds = _load_credentials()
        if not creds:
            raise RuntimeError(
                "Google credentials missing. Run: uv run python -m src.integrations.google_calendar auth"
            )
        self._service = build("calendar", "v3", credentials=creds)
        self._calendar_id = get_settings().google_calendar_id

    async def list_upcoming_events(self, hours: int = 24) -> list[dict]:
        """Get events in the next N hours."""
        now = datetime.utcnow().isoformat() + "Z"
        end = (datetime.utcnow() + timedelta(hours=hours)).isoformat() + "Z"

        def _call():
            return (
                self._service.events()
                .list(
                    calendarId=self._calendar_id,
                    timeMin=now,
                    timeMax=end,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=50,
                )
                .execute()
            )

        result = await asyncio.to_thread(_call)
        return result.get("items", [])

    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: str = "",
        attendees: list[str] | None = None,
    ) -> dict:
        body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
            "attendees": [{"email": a} for a in (attendees or [])],
        }
        logger.info("Creating calendar event: {}", summary)
        return await asyncio.to_thread(
            lambda: self._service.events()
            .insert(calendarId=self._calendar_id, body=body)
            .execute()
        )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        run_oauth_flow()
    else:
        print("Usage: python -m src.integrations.google_calendar auth")
