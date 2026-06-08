"""Storage layer: SQLite engine, session factory, and DB initialisation."""
from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from src.config import get_settings

# Re-export models so callers can do `from src.storage import ReadingListItem`
from src.storage.models import (  # noqa: F401
    AuditLog,
    ChatMessage,
    ChatSession,
    FoodEntry,
    HealthMetricDaily,
    ItemKind,
    ItemStatus,
    PlaidItem,
    PracticeSession,
    ReadingListItem,
    Transaction,
    UsageEvent,
    UserConfig,
    VocabularyEntry,
)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = settings.database_url
        # SQLite needs check_same_thread=False; PostgreSQL does not (and rejects it)
        is_sqlite = db_url.startswith("sqlite")
        connect_args = {"check_same_thread": False} if is_sqlite else {}
        _engine = create_engine(db_url, connect_args=connect_args)
    return _engine


# Public alias
engine = property(_get_engine)


def init_db() -> None:
    """Create all tables (idempotent)."""
    engine = _get_engine()
    SQLModel.metadata.create_all(engine)
    _migrate_schema(engine)
    # Seed user config defaults once tables exist.
    from src.services.user_config import ensure_defaults

    with Session(engine) as session:
        ensure_defaults(session)


def _migrate_schema(engine) -> None:
    """Lightweight migrations for existing local SQLite databases. No-op on PostgreSQL."""
    from sqlalchemy import text

    db_url = str(engine.url)
    if not db_url.startswith("sqlite"):
        return  # PostgreSQL uses SQLModel.metadata.create_all — no manual migrations needed

    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(reading_list_items)")).fetchall()
        columns = {row[1] for row in rows}
        if "content_path" not in columns:
            conn.execute(text("ALTER TABLE reading_list_items ADD COLUMN content_path TEXT"))
            conn.commit()


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""
    with Session(_get_engine()) as session:
        yield session
