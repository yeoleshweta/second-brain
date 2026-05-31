"""Google People API client (contacts.readonly scope).

Reuses the same OAuth token as the Calendar client — the `contacts.readonly`
scope is already included in SCOPES in google_calendar.py.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from googleapiclient.discovery import build
from loguru import logger

from src.integrations.google_calendar import _load_credentials


class GooglePeopleClient:
    def __init__(self) -> None:
        creds = _load_credentials()
        if not creds:
            raise RuntimeError(
                "Google credentials missing. "
                "Run: uv run python -m src.integrations.google_calendar auth"
            )
        self._service = build("people", "v1", credentials=creds)

    async def search_contacts(self, query: str) -> list[dict]:
        """Search user's Google Contacts. Returns simplified dicts."""
        def _call():
            return (
                self._service.people()
                .searchContacts(
                    query=query,
                    readMask="names,emailAddresses,phoneNumbers,organizations",
                    pageSize=10,
                )
                .execute()
            )

        try:
            result = await asyncio.to_thread(_call)
        except Exception as e:
            logger.warning("Google People search failed: {}", e)
            return []

        contacts = []
        for item in result.get("results", []):
            person = item.get("person", {})
            names = person.get("names", [])
            name = names[0].get("displayName", "") if names else ""
            emails = [e["value"] for e in person.get("emailAddresses", [])]
            phones = [p["value"] for p in person.get("phoneNumbers", [])]
            orgs = person.get("organizations", [])
            org_name = orgs[0].get("name", "") if orgs else ""
            org_title = orgs[0].get("title", "") if orgs else ""
            contacts.append({
                "name": name,
                "emails": emails,
                "phones": phones,
                "organization": org_name,
                "role": org_title,
            })
        return contacts

    async def get_contact_by_email(self, email: str) -> dict | None:
        """Look up a single contact by email address."""
        results = await self.search_contacts(email)
        for c in results:
            if email.lower() in [e.lower() for e in c.get("emails", [])]:
                return c
        return None
