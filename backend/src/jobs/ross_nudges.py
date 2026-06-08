"""Ross proactive nudges and weekly review jobs."""
from __future__ import annotations

from datetime import datetime, timedelta

from loguru import logger
from sqlmodel import Session, select

from src.agents.knowledge import handle_digest_now
from src.integrations.obsidian import ObsidianClient
from src.services import practice, reading_list, user_config
from src.storage import get_session
from src.storage.models import AuditLog, ItemStatus, ReadingListItem


async def _append_line_to_today_note(line: str) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    path = f"00-Inbox/Daily/{today}-Brief.md"

    async with ObsidianClient() as obsidian:
        try:
            existing = await obsidian.get_note(path)
        except Exception:
            existing = f"# Morning Brief — {today}\n\n"
        await obsidian.create_note(path, existing.rstrip() + "\n\n" + line + "\n")


def _is_allowed(session: Session, channel_key: str) -> bool:
    if user_config.nudges_paused(session):
        return False
    if user_config.within_quiet_hours(session):
        return False
    return user_config.get_bool(session, channel_key, True)


async def send_midday_reading_prompt() -> None:
    with next(get_session()) as session:
        if not _is_allowed(session, "nudge_mid_day_reading"):
            return
        goal = user_config.get_int(session, "daily_reading_minutes_goal", 15)
        if goal <= 0:
            return
        # Proxy reading minutes from explicit "reading" practice logs.
        today = datetime.now().date()
        today_rows = [
            r for r in practice.last_days(session, days=1) if r.logged_at.date() == today
        ]
        reading_minutes = sum(r.minutes for r in today_rows if r.skill in {"reading", "read"})
        if reading_minutes >= max(1, goal // 2):
            return
        picks = [i.title for i in reading_list.list_active(session)[:3]]
        if not picks:
            return
        text = (
            "### Mid-day prompt\n"
            "You haven't read yet today. 3 candidates from your list, ~10 min each:\n"
            + "\n".join([f"- {p}" for p in picks])
            + "\n\nWant one queued up?"
        )
        await _append_line_to_today_note(text)


async def send_evening_reading_checkin() -> None:
    with next(get_session()) as session:
        if not _is_allowed(session, "nudge_evening_reading"):
            return
        goal = user_config.get_int(session, "daily_reading_minutes_goal", 15)
        if goal <= 0:
            return
        today = datetime.now().date()
        today_rows = [
            r for r in practice.last_days(session, days=1) if r.logged_at.date() == today
        ]
        reading_minutes = sum(r.minutes for r in today_rows if r.skill in {"reading", "read"})
        if reading_minutes >= goal:
            return
        remaining = max(0, goal - reading_minutes)
        in_progress = next(
            (i for i in reading_list.list_active(session) if i.status == ItemStatus.IN_PROGRESS),
            None,
        )
        title = in_progress.title if in_progress else "something from your list"
        await _append_line_to_today_note(
            f"### Evening check-in\nYou're {remaining} min short of today's "
            f"{goal}-min reading goal. Want to finish '{title}'?"
        )


async def send_practice_nudge() -> None:
    with next(get_session()) as session:
        if not _is_allowed(session, "nudge_evening_practice"):
            return
        today = datetime.now().date()
        yday = today - timedelta(days=1)
        today_minutes = practice.today_total(session, day=today)
        yday_minutes = practice.today_total(session, day=yday)
        if today_minutes > 0 or yday_minutes == 0:
            return
        await _append_line_to_today_note(
            "### Practice nudge\nNo practice logged today. 30 min still counts."
        )


async def write_weekly_review() -> str:
    with next(get_session()) as session:
        if not _is_allowed(session, "nudge_weekly_review"):
            return ""
        now = datetime.now()
        since = now - timedelta(days=7)
        read_items = reading_list.list_finished_since(session, since)
        practice_stats = practice.weekly_breakdown(session, days=7)
        unread = reading_list.list_active(session)

        path = f"00-Inbox/Daily/{now.strftime('%Y-%m-%d')}-Weekly.md"
        lines = [
            f"# Weekly Review — {now.strftime('%Y-%m-%d')}",
            "",
            f"- Articles read: {len(read_items)}",
            f"- Practice days: {practice_stats['active_days']}",
            f"- Practice minutes: {practice_stats['total_minutes']}",
            "",
            "## Read this week",
        ]
        for item in read_items[:12]:
            lines.append(f"- {item.title} ({item.source or item.kind})")
        lines += ["", "## Saved but unread"]
        for item in unread[:12]:
            lines.append(f"- {item.title}")
        if unread:
            lines += ["", "## Suggested focus next week", f"- Read: {unread[0].title}"]
        if practice_stats.get("top_skill"):
            lines.append(f"- Practice: prioritize {practice_stats['top_skill']}")
        content = "\n".join(lines) + "\n"

    async with ObsidianClient() as obs:
        await obs.create_note(path, content)
    return path


async def send_stale_in_progress_ping() -> None:
    with next(get_session()) as session:
        stale = list(
            session.exec(
                select(ReadingListItem).where(
                    ReadingListItem.status == ItemStatus.IN_PROGRESS,  # type: ignore[attr-defined]
                    ReadingListItem.saved_at <= datetime.now() - timedelta(days=14),  # type: ignore[attr-defined]
                )
            ).all()
        )
        for item in stale[:3]:
            marker = f"stale_ping:{item.id}"
            sent = session.exec(
                select(AuditLog).where(
                    AuditLog.agent == "ross",
                    AuditLog.action == marker,
                )
            ).first()
            if sent:
                continue
            await _append_line_to_today_note(
                "### In-progress check\n"
                f"'{item.title}' has been in progress for 14+ days. Drop it or finish?"
            )
            session.add(AuditLog(agent="ross", action=marker, payload=item.title, success=True))
            session.commit()


async def send_discovery_suggestions() -> None:
    with next(get_session()) as session:
        if not _is_allowed(session, "nudge_discovery"):
            return
    digest = await handle_digest_now()
    items = digest.get("digest_items", [])[:3]
    if not items:
        return
    block = "### Discovery picks\n" + "\n".join([f"- {i['title']}" for i in items])
    await _append_line_to_today_note(block)
    logger.info("Ross discovery suggestions prepared")
