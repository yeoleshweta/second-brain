"""User configuration service for Ross v2."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session, select

from src.storage.models import UserConfig

DEFAULTS: dict[str, str] = {
    "daily_reading_minutes_goal": "15",
    "daily_practice_minutes_goal": "60",
    "active_skills": "guitar,system-design,coding",
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "06:00",
    "nudges_paused_until": "",
    "mid_day_nudge_time": "14:00",
    "evening_nudge_time": "21:00",
    "practice_nudge_time": "19:00",
    "nudge_morning_brief": "true",
    "nudge_mid_day_reading": "true",
    "nudge_evening_reading": "true",
    "nudge_evening_practice": "true",
    "nudge_weekly_review": "true",
    "nudge_discovery": "true",
}


def ensure_defaults(session: Session) -> None:
    changed = False
    for key, value in DEFAULTS.items():
        row = session.get(UserConfig, key)
        if row is None:
            session.add(UserConfig(key=key, value=value))
            changed = True
    if changed:
        session.commit()


def get(session: Session, key: str, fallback: str | None = None) -> str | None:
    row = session.get(UserConfig, key)
    if row is not None:
        return row.value
    return DEFAULTS.get(key, fallback)


def set_value(session: Session, key: str, value: str) -> None:
    row = session.get(UserConfig, key)
    if row is None:
        row = UserConfig(key=key, value=value)
    else:
        row.value = value
    session.add(row)
    session.commit()


def all_values(session: Session) -> dict[str, str]:
    rows = session.exec(select(UserConfig)).all()
    out = {k: v for k, v in DEFAULTS.items()}
    out.update({r.key: r.value for r in rows})
    return out


def get_int(session: Session, key: str, default: int) -> int:
    raw = get(session, key)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def get_bool(session: Session, key: str, default: bool = True) -> bool:
    raw = (get(session, key) or "").strip().lower()
    if raw in {"true", "1", "yes", "y", "on"}:
        return True
    if raw in {"false", "0", "no", "n", "off"}:
        return False
    return default


def active_skills(session: Session) -> list[str]:
    raw = get(session, "active_skills", "") or ""
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


def set_active_skills(session: Session, skills: list[str]) -> None:
    normalized = [s.strip().lower() for s in skills if s.strip()]
    deduped = list(dict.fromkeys(normalized))
    set_value(session, "active_skills", ",".join(deduped))


def pause_nudges(session: Session, hours: int) -> datetime:
    until = datetime.now() + timedelta(hours=hours)
    set_value(session, "nudges_paused_until", until.isoformat())
    return until


def nudges_paused(session: Session) -> bool:
    raw = get(session, "nudges_paused_until", "") or ""
    if not raw:
        return False
    try:
        until = datetime.fromisoformat(raw)
    except ValueError:
        return False
    return until > datetime.now()


def within_quiet_hours(session: Session, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    start = get(session, "quiet_hours_start", "22:00") or "22:00"
    end = get(session, "quiet_hours_end", "06:00") or "06:00"
    try:
        start_h, start_m = [int(x) for x in start.split(":", 1)]
        end_h, end_m = [int(x) for x in end.split(":", 1)]
    except ValueError:
        return False

    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m
    now_minutes = now.hour * 60 + now.minute

    if start_minutes <= end_minutes:
        return start_minutes <= now_minutes < end_minutes
    # Overnight window (e.g. 22:00 -> 06:00)
    return now_minutes >= start_minutes or now_minutes < end_minutes
