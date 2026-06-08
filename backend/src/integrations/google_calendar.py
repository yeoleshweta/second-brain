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

from googleapiclient.discovery import build
from loguru import logger

from src.config import get_settings
from src.integrations.google_auth import load_google_credentials, run_google_oauth_flow


class GoogleCalendarClient:
    def __init__(self) -> None:
        creds = load_google_credentials()
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

    async def get_event(self, event_id: str) -> dict:
        return await asyncio.to_thread(
            lambda: self._service.events()
            .get(calendarId=self._calendar_id, eventId=event_id)
            .execute()
        )

    async def update_event(self, event_id: str, **kwargs) -> dict:
        existing = await self.get_event(event_id)
        existing.update(kwargs)
        return await asyncio.to_thread(
            lambda: self._service.events()
            .update(calendarId=self._calendar_id, eventId=event_id, body=existing)
            .execute()
        )

    async def delete_event(self, event_id: str) -> None:
        await asyncio.to_thread(
            lambda: self._service.events()
            .delete(calendarId=self._calendar_id, eventId=event_id)
            .execute()
        )
        logger.info("Deleted calendar event {}", event_id)

    async def health_check(self) -> dict:
        """Verify API connectivity; returns {status:'ok'} or {status:'error', detail:...}."""
        try:
            await asyncio.to_thread(
                lambda: self._service.events()
                .list(calendarId=self._calendar_id, maxResults=1)
                .execute()
            )
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}


def google_calendar_status() -> dict:
    """Return health status dict without raising — safe to call from API handlers."""
    settings = get_settings()
    client_secrets = settings.google_oauth_client_secrets
    token_path = settings.google_token_path

    if not client_secrets or not Path(client_secrets).exists():
        return {
            "status": "not_configured",
            "detail": (
                "Missing google_client_secret.json. "
                "See docs/phase-2-iphone-setup.md for setup instructions."
            ),
        }
    if not token_path or not Path(token_path).exists():
        return {
            "status": "not_authenticated",
            "detail": (
                "Google not authorized yet. "
                "Run: cd backend && uv run python -m src.integrations.google_calendar auth"
            ),
        }
    try:
        client = GoogleCalendarClient()
        return asyncio.get_event_loop().run_until_complete(client.health_check())
    except Exception as e:
        return {"status": "error", "detail": str(e)}


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        run_google_oauth_flow()
    else:
        print("Usage: python -m src.integrations.google_calendar auth")
