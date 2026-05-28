"""Storage layer: SQLite engine, session factory, and DB initialisation."""
from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from src.config import get_settings

# Re-export models so callers can do `from src.storage import ReadingListItem`
from src.storage.models import (  # noqa: F401
    AuditLog,
    FoodEntry,
    HealthMetricDaily,
    ItemKind,
    ItemStatus,
    PlaidItem,
    ReadingListItem,
    Transaction,
)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
        )
    return _engine


# Public alias
engine = property(_get_engine)


def init_db() -> None:
    """Create all tables (idempotent)."""
    SQLModel.metadata.create_all(_get_engine())


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""
    with Session(_get_engine()) as session:
        yield session
