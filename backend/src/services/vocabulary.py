"""Vocabulary tracking for knowledge building."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session, select

from src.storage.models import ItemKind, ItemStatus, ReadingListItem, VocabularyEntry


def add_word(
    session: Session,
    *,
    word: str,
    definition: str,
    context: str | None = None,
    source_title: str | None = None,
    source_item_id: int | None = None,
    tags: str = "",
) -> VocabularyEntry:
    entry = VocabularyEntry(
        word=word.strip().lower(),
        definition=definition.strip(),
        context=context,
        source_title=source_title,
        source_item_id=source_item_id,
        tags=tags,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def list_recent(session: Session, *, limit: int = 20) -> list[VocabularyEntry]:
    return list(
        session.exec(
            select(VocabularyEntry)
            .order_by(VocabularyEntry.logged_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
        ).all()
    )


def list_by_tag(session: Session, tag: str, *, limit: int = 30) -> list[VocabularyEntry]:
    tag_norm = tag.strip().lower()
    items = list_recent(session, limit=200)
    return [
        item
        for item in items
        if tag_norm in {t.strip().lower() for t in (item.tags or "").split(",") if t.strip()}
    ][:limit]


def stats(session: Session) -> dict:
    all_words = list(session.exec(select(VocabularyEntry)).all())
    week_ago = datetime.now() - timedelta(days=7)
    this_week = sum(1 for w in all_words if w.logged_at >= week_ago)
    tags: set[str] = set()
    for w in all_words:
        for t in (w.tags or "").split(","):
            if t.strip():
                tags.add(t.strip().lower())
    books = list(
        session.exec(
            select(ReadingListItem).where(
                ReadingListItem.kind.in_([ItemKind.EBOOK, ItemKind.AUDIOBOOK])  # type: ignore[attr-defined]
            )
        ).all()
    )
    books_read = sum(1 for b in books if b.status == ItemStatus.READ)
    return {
        "total_words": len(all_words),
        "words_this_week": this_week,
        "topic_tags": sorted(tags)[:20],
        "ebooks_saved": len(books),
        "ebooks_read": books_read,
    }
