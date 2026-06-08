"""Reading list service — all DB operations for ReadingListItem."""
from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from src.storage.models import ItemKind, ItemStatus, ReadingListItem


def add(
    session: Session,
    *,
    url: str | None = None,
    title: str,
    summary: str | None = None,
    source: str | None = None,
    kind: ItemKind = ItemKind.URL,
    tags: str = "",
    content_path: str | None = None,
) -> ReadingListItem | None:
    """Insert a new item. Returns None if a URL already exists (dedup)."""
    if url:
        existing = session.exec(
            select(ReadingListItem).where(ReadingListItem.url == url)
        ).first()
        if existing:
            return None

    item = ReadingListItem(
        url=url,
        title=title,
        summary=summary,
        source=source,
        kind=kind,
        tags=tags,
        content_path=content_path,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def list_active(session: Session) -> list[ReadingListItem]:
    """Unread + in-progress items, newest first."""
    return list(
        session.exec(
            select(ReadingListItem)
            .where(ReadingListItem.status.in_([ItemStatus.UNREAD, ItemStatus.IN_PROGRESS]))  # type: ignore[attr-defined]
            .order_by(ReadingListItem.saved_at.desc())  # type: ignore[attr-defined]
        ).all()
    )


def list_all(session: Session) -> list[ReadingListItem]:
    """All items, newest first."""
    return list(
        session.exec(
            select(ReadingListItem).order_by(ReadingListItem.saved_at.desc())  # type: ignore[attr-defined]
        ).all()
    )


def find_by_id(session: Session, item_id: int) -> ReadingListItem | None:
    return session.get(ReadingListItem, item_id)


def find_by_title(session: Session, query: str) -> ReadingListItem | None:
    """Fuzzy title match — returns the most recently saved match."""
    q = f"%{query.lower()}%"
    results = list(
        session.exec(
            select(ReadingListItem)
            .where(ReadingListItem.title.ilike(q))  # type: ignore[attr-defined]
            .order_by(ReadingListItem.saved_at.desc())  # type: ignore[attr-defined]
        ).all()
    )
    return results[0] if results else None


def search_by_title(
    session: Session,
    query: str,
    *,
    statuses: tuple[ItemStatus, ...] | None = None,
    limit: int = 10,
) -> list[ReadingListItem]:
    q = f"%{query.lower()}%"
    stmt = select(ReadingListItem).where(ReadingListItem.title.ilike(q))  # type: ignore[attr-defined]
    if statuses:
        stmt = stmt.where(ReadingListItem.status.in_(list(statuses)))  # type: ignore[attr-defined]
    stmt = stmt.order_by(ReadingListItem.saved_at.desc()).limit(limit)  # type: ignore[attr-defined]
    return list(session.exec(stmt).all())


def list_by_tag(session: Session, tag: str, *, only_active: bool = True) -> list[ReadingListItem]:
    tag_norm = tag.strip().lower()
    items = list_active(session) if only_active else list_all(session)
    return [
        i
        for i in items
        if tag_norm in {t.strip().lower() for t in (i.tags or "").split(",") if t.strip()}
    ]


def list_finished_since(session: Session, since: datetime) -> list[ReadingListItem]:
    return list(
        session.exec(
            select(ReadingListItem)
            .where(
                ReadingListItem.status == ItemStatus.READ,  # type: ignore[attr-defined]
                ReadingListItem.finished_at >= since,  # type: ignore[attr-defined]
            )
            .order_by(ReadingListItem.finished_at.desc())  # type: ignore[attr-defined]
        ).all()
    )


def mark_read(session: Session, item: ReadingListItem) -> ReadingListItem:
    item.status = ItemStatus.READ
    item.finished_at = datetime.now()
    item.progress = 100
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def update_progress(session: Session, item: ReadingListItem, pct: int) -> ReadingListItem:
    pct = max(0, min(100, pct))
    item.progress = pct
    if pct == 100:
        item.status = ItemStatus.READ
        item.finished_at = item.finished_at or datetime.now()
    elif pct > 0:
        item.status = ItemStatus.IN_PROGRESS
    else:
        item.status = ItemStatus.UNREAD
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def delete(session: Session, item: ReadingListItem) -> None:
    from src.services.reading_content import delete_item_content

    item_id = item.id
    session.delete(item)
    session.commit()
    if item_id is not None:
        delete_item_content(item_id)


def stats(session: Session) -> dict:
    all_items = list_all(session)
    total = len(all_items)
    read = sum(1 for i in all_items if i.status == ItemStatus.READ)
    in_progress = sum(1 for i in all_items if i.status == ItemStatus.IN_PROGRESS)
    unread = sum(1 for i in all_items if i.status == ItemStatus.UNREAD)
    percent_done = round(read / total * 100) if total else 0
    return {
        "total": total,
        "read": read,
        "in_progress": in_progress,
        "unread": unread,
        "percent_done": percent_done,
    }
