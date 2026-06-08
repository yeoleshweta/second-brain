"""Fernet encryption for sensitive tokens (Plaid access tokens)."""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from src.config import get_settings


def mask_secret(value: str) -> str:
    if len(value) < 9:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def _fernet() -> Fernet:
    key = get_settings().plaid_token_encryption_key
    if not key:
        raise RuntimeError(
            "PLAID_TOKEN_ENCRYPTION_KEY not set — generate with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode("utf-8"))


def encrypt_token(plain: str) -> bytes:
    return _fernet().encrypt(plain.encode("utf-8"))


def decrypt_token(encrypted: bytes) -> str:
    try:
        return _fernet().decrypt(encrypted).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError(
            "Failed to decrypt Plaid token — check PLAID_TOKEN_ENCRYPTION_KEY"
        ) from exc
