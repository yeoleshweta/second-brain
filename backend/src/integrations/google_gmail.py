"""Gmail read-only integration for Chandler inbox triage."""
from __future__ import annotations

import asyncio
from email.utils import parseaddr

from googleapiclient.discovery import build
from loguru import logger

from src.integrations.google_auth import load_google_credentials


class GmailClient:
    def __init__(self) -> None:
        creds = load_google_credentials()
        if not creds:
            raise RuntimeError(
                "Google credentials missing. Run: "
                "cd backend && uv run python -m src.integrations.google_calendar auth"
            )
        self._service = build("gmail", "v1", credentials=creds)

    async def list_unread_important(self, max_results: int = 8) -> list[dict]:
        """Return recent unread inbox messages (subject, from, snippet)."""

        def _call() -> list[dict]:
            listed = (
                self._service.users()
                .messages()
                .list(
                    userId="me",
                    labelIds=["INBOX", "UNREAD"],
                    maxResults=max_results,
                )
                .execute()
            )
            out: list[dict] = []
            for meta in listed.get("messages", []):
                msg = (
                    self._service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=meta["id"],
                        format="metadata",
                        metadataHeaders=["From", "Subject"],
                    )
                    .execute()
                )
                headers = {
                    h["name"].lower(): h["value"]
                    for h in msg.get("payload", {}).get("headers", [])
                }
                from_raw = headers.get("from", "")
                _, from_email = parseaddr(from_raw)
                out.append(
                    {
                        "id": msg["id"],
                        "subject": headers.get("subject", "(no subject)"),
                        "from": from_raw or from_email,
                        "from_email": from_email,
                        "snippet": msg.get("snippet", ""),
                    }
                )
            return out

        return await asyncio.to_thread(_call)


async def gmail_morning_section() -> str:
    """Markdown section for the combined morning brief."""
    try:
        client = GmailClient()
        messages = await client.list_unread_important(max_results=6)
    except Exception as exc:
        logger.warning("Gmail morning section failed: {}", exc)
        return f"## 📧 Gmail\n\nCouldn't read inbox — {exc}\n"

    if not messages:
        return "## 📧 Gmail\n\nInbox zero (no unread messages).\n"

    lines = ["## 📧 Gmail — unread\n"]
    for msg in messages:
        who = msg.get("from") or msg.get("from_email") or "Unknown"
        subj = msg.get("subject", "(no subject)")
        snippet = (msg.get("snippet") or "").replace("\n", " ")[:120]
        lines.append(f"- **{subj}** — {who}")
        if snippet:
            lines.append(f"  _{snippet}_")
    return "\n".join(lines) + "\n"
