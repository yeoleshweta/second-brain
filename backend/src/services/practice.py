"""Practice tracking service."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlmodel import Session, select

from src.storage.models import PracticeSession


def log(
    session: Session,
    *,
    skill: str,
    minutes: int,
    notes: str | None = None,
    via: str = "chat",
) -> PracticeSession:
    item = PracticeSession(
        skill=skill.strip().lower(),
        minutes=max(1, minutes),
        notes=notes,
        via=via,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def today_total(session: Session, day: date | None = None) -> int:
    day = day or date.today()
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    rows = session.exec(
        select(PracticeSession).where(
            PracticeSession.logged_at >= start,
            PracticeSession.logged_at < end,
        )
    ).all()
    return sum(r.minutes for r in rows)


def last_days(session: Session, days: int = 7) -> list[PracticeSession]:
    since = datetime.now() - timedelta(days=days)
    return list(
        session.exec(
            select(PracticeSession)
            .where(PracticeSession.logged_at >= since)
            .order_by(PracticeSession.logged_at.desc())  # type: ignore[attr-defined]
        ).all()
    )


def weekly_breakdown(session: Session, days: int = 7) -> dict:
    rows = last_days(session, days=days)
    by_day: dict[str, int] = {}
    by_skill: dict[str, int] = {}
    for row in rows:
        key = row.logged_at.date().isoformat()
        by_day[key] = by_day.get(key, 0) + row.minutes
        by_skill[row.skill] = by_skill.get(row.skill, 0) + row.minutes

    active_days = sum(1 for _, mins in by_day.items() if mins > 0)
    total_minutes = sum(by_day.values())
    top_skill = max(by_skill, key=by_skill.get) if by_skill else None
    return {
        "days_window": days,
        "active_days": active_days,
        "total_minutes": total_minutes,
        "by_day": by_day,
        "by_skill": by_skill,
        "top_skill": top_skill,
    }
