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
from plaid.api_client import ApiClient
from plaid.configuration import Configuration
from plaid.model.country_code import CountryCode
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.item_get_request import ItemGetRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest

from src.config import get_settings
from src.services.token_crypto import mask_secret

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

    async def exchange_public_token(self, public_token: str) -> dict:
        """Exchange the one-time public_token for a long-lived access_token."""
        req = ItemPublicTokenExchangeRequest(public_token=public_token)
        resp = await asyncio.to_thread(self._api.item_public_token_exchange, req)
        access_token = resp["access_token"]
        item_id = resp["item_id"]
        institution_name = await self.get_institution_name(access_token)
        logger.info(
            "Plaid item linked: item_id={} institution={} token={}",
            item_id,
            institution_name,
            mask_secret(access_token),
        )
        return {
            "access_token": access_token,
            "item_id": item_id,
            "institution_name": institution_name,
        }

    async def get_institution_name(self, access_token: str) -> str:
        item_resp = await asyncio.to_thread(
            self._api.item_get,
            ItemGetRequest(access_token=access_token),
        )
        institution_id = item_resp["item"].get("institution_id")
        if not institution_id:
            return "Linked bank"

        countries = [
            CountryCode(c.strip()) for c in self._settings.plaid_country_codes.split(",")
        ]
        inst_resp = await asyncio.to_thread(
            self._api.institutions_get_by_id,
            InstitutionsGetByIdRequest(
                institution_id=institution_id,
                country_codes=countries,
            ),
        )
        return inst_resp["institution"]["name"]

    async def remove_item(self, access_token: str) -> None:
        await asyncio.to_thread(
            self._api.item_remove,
            ItemRemoveRequest(access_token=access_token),
        )

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
