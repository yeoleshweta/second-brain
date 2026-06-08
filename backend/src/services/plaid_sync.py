"""Sync Plaid transactions for all linked items into the local Transaction table.

Usage:
    from src.services.plaid_sync import sync_all_items
    await sync_all_items(session)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger
from sqlmodel import Session, select

from src.integrations.plaid_client import PlaidClient
from src.services.plaid_items import access_token_for_item, list_items
from src.storage.models import PlaidItem, Transaction


def _parse_date(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw
    if hasattr(raw, "isoformat"):  # date object
        return datetime(raw.year, raw.month, raw.day)
    return datetime.fromisoformat(str(raw))


def _upsert_transaction(session: Session, tx: Any, item_id: str) -> bool:
    """Insert or update one Plaid transaction. Returns True if new."""
    plaid_id = tx.get("transaction_id") or tx.get("id")
    if not plaid_id:
        return False

    existing = session.exec(
        select(Transaction).where(Transaction.plaid_transaction_id == plaid_id)
    ).first()

    merchant = (
        tx.get("merchant_name")
        or tx.get("name")
        or tx.get("original_description")
        or "Unknown"
    )
    cats: list[str] = tx.get("personal_finance_category", {}).get("detailed", None) or (
        tx.get("category") or []
    )
    category = cats[0] if isinstance(cats, list) and cats else (cats or None)
    raw_category = ", ".join(cats) if isinstance(cats, list) else str(cats or "")
    amount = float(tx.get("amount", 0))
    pending = bool(tx.get("pending", False))
    account_id = tx.get("account_id", "")
    date = _parse_date(tx.get("date") or tx.get("authorized_date") or datetime.now())

    if existing:
        existing.merchant = merchant
        existing.category = category
        existing.raw_category = raw_category
        existing.amount = amount
        existing.pending = pending
        session.add(existing)
        return False

    row = Transaction(
        plaid_transaction_id=plaid_id,
        account_id=account_id,
        date=date,
        amount=amount,
        merchant=merchant,
        category=category,
        raw_category=raw_category,
        pending=pending,
    )
    session.add(row)
    return True


def _remove_transaction(session: Session, plaid_id: str) -> None:
    row = session.exec(
        select(Transaction).where(Transaction.plaid_transaction_id == plaid_id)
    ).first()
    if row:
        session.delete(row)


async def sync_item(session: Session, item: PlaidItem) -> dict:
    """Sync one Plaid Item. Returns stats dict."""
    access_token = access_token_for_item(item)
    client = PlaidClient()

    added_count = modified_count = removed_count = 0
    cursor = item.cursor

    while True:
        data = await client.sync_transactions(access_token, cursor=cursor)
        for tx in data["added"]:
            if _upsert_transaction(session, tx, item.item_id):
                added_count += 1
        for tx in data["modified"]:
            _upsert_transaction(session, tx, item.item_id)
            modified_count += 1
        for tx in data["removed"]:
            plaid_id = tx.get("transaction_id") or tx.get("id", "")
            _remove_transaction(session, plaid_id)
            removed_count += 1

        cursor = data["next_cursor"]
        if not data["has_more"]:
            break

    item.cursor = cursor
    session.add(item)
    session.commit()

    stats = {
        "item_id": item.item_id,
        "institution": item.institution_name,
        "added": added_count,
        "modified": modified_count,
        "removed": removed_count,
    }
    logger.info("Plaid sync complete: {}", stats)
    return stats


async def sync_all_items(session: Session) -> list[dict]:
    """Sync every linked Plaid Item. Returns per-item stats."""
    items = list_items(session)
    if not items:
        logger.info("No Plaid items linked; skipping sync")
        return []

    results: list[dict] = []
    for item in items:
        try:
            stats = await sync_item(session, item)
            results.append({"status": "ok", **stats})
        except Exception as exc:
            logger.error("Plaid sync failed for {}: {}", item.institution_name, exc)
            results.append(
                {
                    "status": "error",
                    "item_id": item.item_id,
                    "institution": item.institution_name,
                    "error": str(exc),
                }
            )
    return results
