"""Persist linked Plaid Items (encrypted access tokens in SQLite)."""
from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from src.services.token_crypto import decrypt_token, encrypt_token
from src.storage.models import PlaidItem


def list_items(session: Session) -> list[PlaidItem]:
    return list(session.exec(select(PlaidItem).order_by(PlaidItem.linked_at.desc())).all())


def get_by_item_id(session: Session, item_id: str) -> PlaidItem | None:
    return session.exec(select(PlaidItem).where(PlaidItem.item_id == item_id)).first()


def upsert_item(
    session: Session,
    *,
    item_id: str,
    institution_name: str,
    access_token: str,
) -> PlaidItem:
    encrypted = encrypt_token(access_token)
    existing = get_by_item_id(session, item_id)
    if existing:
        existing.institution_name = institution_name
        existing.access_token_encrypted = encrypted
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    row = PlaidItem(
        item_id=item_id,
        institution_name=institution_name,
        access_token_encrypted=encrypted,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def delete_item(session: Session, item_id: str) -> PlaidItem | None:
    row = get_by_item_id(session, item_id)
    if not row:
        return None
    session.delete(row)
    session.commit()
    return row


def access_token_for_item(row: PlaidItem) -> str:
    return decrypt_token(row.access_token_encrypted)


def item_summary(row: PlaidItem) -> dict:
    linked_at = row.linked_at
    if isinstance(linked_at, datetime):
        linked_at = linked_at.isoformat()
    return {
        "item_id": row.item_id,
        "institution_name": row.institution_name,
        "linked_at": linked_at,
    }
