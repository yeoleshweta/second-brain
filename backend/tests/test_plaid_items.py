"""Plaid token encryption and item persistence tests."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlmodel import Session, SQLModel, create_engine

from src.config.settings import get_settings
from src.services import plaid_items as pi
from src.services.token_crypto import decrypt_token, encrypt_token, mask_secret

_TEST_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLAID_TOKEN_ENCRYPTION_KEY", _TEST_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_mask_secret() -> None:
    assert mask_secret("abcdefghijklmnop") == "abcd...mnop"
    assert mask_secret("short") == "****"


def test_encrypt_decrypt_roundtrip() -> None:
    plain = "access-sandbox-deadbeef"
    encrypted = encrypt_token(plain)
    assert encrypted != plain.encode()
    assert decrypt_token(encrypted) == plain


def test_upsert_and_list_items(session: Session) -> None:
    row = pi.upsert_item(
        session,
        item_id="item_123",
        institution_name="First Platypus Bank",
        access_token="access-sandbox-test-token-value",
    )
    assert row.id is not None
    assert row.institution_name == "First Platypus Bank"

    items = pi.list_items(session)
    assert len(items) == 1
    assert pi.access_token_for_item(items[0]) == "access-sandbox-test-token-value"

    updated = pi.upsert_item(
        session,
        item_id="item_123",
        institution_name="First Platypus Bank",
        access_token="access-sandbox-new-token-value",
    )
    assert updated.id == row.id
    assert pi.access_token_for_item(updated) == "access-sandbox-new-token-value"


def test_delete_item(session: Session) -> None:
    pi.upsert_item(
        session,
        item_id="item_del",
        institution_name="Test Bank",
        access_token="access-sandbox-delete-me",
    )
    removed = pi.delete_item(session, "item_del")
    assert removed is not None
    assert pi.get_by_item_id(session, "item_del") is None


def test_item_summary(session: Session) -> None:
    row = pi.upsert_item(
        session,
        item_id="item_sum",
        institution_name="Summary Bank",
        access_token="access-sandbox-summary",
    )
    summary = pi.item_summary(row)
    assert summary["item_id"] == "item_sum"
    assert summary["institution_name"] == "Summary Bank"
    assert "linked_at" in summary
