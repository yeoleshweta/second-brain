"""Plaid integration for finance.

Plaid auth flow (one-time per bank):
  1. Backend creates a link_token (/plaid/link-token endpoint)
  2. Frontend uses Plaid Link UI with that token (user picks bank, logs in)
  3. Plaid returns a public_token to the frontend
  4. Frontend sends public_token to backend
  5. Backend exchanges it for an access_token (long-lived)
  6. Store access_token encrypted in SQLite per Item

After auth, use /transactions/sync to keep transactions current. NEVER move money.
"""
from __future__ import annotations

import asyncio

from loguru import logger
from plaid.api import plaid_api
from plaid.configuration import Configuration
from plaid.api_client import ApiClient
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest

from src.config import get_settings

_PLAID_HOSTS = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}


class PlaidClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not (settings.plaid_client_id and settings.plaid_secret):
            raise RuntimeError("PLAID_CLIENT_ID / PLAID_SECRET not set")

        config = Configuration(
            host=_PLAID_HOSTS[settings.plaid_env],
            api_key={"clientId": settings.plaid_client_id, "secret": settings.plaid_secret},
        )
        self._api = plaid_api.PlaidApi(ApiClient(config))
        self._settings = settings

    async def create_link_token(self, user_id: str) -> str:
        """Create a link_token for the frontend to use in Plaid Link UI."""
        products = [Products(p.strip()) for p in self._settings.plaid_products.split(",")]
        countries = [
            CountryCode(c.strip()) for c in self._settings.plaid_country_codes.split(",")
        ]
        req = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id=user_id),
            client_name="Second Brain",
            products=products,
            country_codes=countries,
            language="en",
        )
        resp = await asyncio.to_thread(self._api.link_token_create, req)
        return resp["link_token"]

    async def exchange_public_token(self, public_token: str) -> str:
        """Exchange the one-time public_token from frontend for a long-lived access_token."""
        req = ItemPublicTokenExchangeRequest(public_token=public_token)
        resp = await asyncio.to_thread(self._api.item_public_token_exchange, req)
        logger.info("Plaid item linked: item_id={}", resp["item_id"])
        return resp["access_token"]

    async def sync_transactions(
        self, access_token: str, cursor: str | None = None
    ) -> dict:
        """Pull new/modified/removed transactions since the last cursor."""
        req = TransactionsSyncRequest(access_token=access_token)
        if cursor:
            req.cursor = cursor
        resp = await asyncio.to_thread(self._api.transactions_sync, req)
        return {
            "added": resp["added"],
            "modified": resp["modified"],
            "removed": resp["removed"],
            "next_cursor": resp["next_cursor"],
            "has_more": resp["has_more"],
        }
