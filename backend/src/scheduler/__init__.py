"""Application scheduler setup."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    from src.jobs.combined_brief import build_combined_brief
    from src.jobs.reachout import append_reachout_to_brief
    from src.jobs.ross_nudges import (
        send_discovery_suggestions,
        send_evening_reading_checkin,
        send_midday_reading_prompt,
        send_practice_nudge,
        send_stale_in_progress_ping,
        write_weekly_review,
    )
    from src.services import user_config
    from src.storage import get_session

    scheduler = AsyncIOScheduler()

    with next(get_session()) as session:
        mid_day = user_config.get(session, "mid_day_nudge_time", "14:00") or "14:00"
        evening = user_config.get(session, "evening_nudge_time", "21:00") or "21:00"
        practice = user_config.get(session, "practice_nudge_time", "19:00") or "19:00"
    mid_h, mid_m = [int(x) for x in mid_day.split(":", 1)]
    eve_h, eve_m = [int(x) for x in evening.split(":", 1)]
    prac_h, prac_m = [int(x) for x in practice.split(":", 1)]

    # Daily at 06:00 — combined (Chandler + Ross) morning brief
    scheduler.add_job(
        build_combined_brief,
        trigger="cron",
        hour=6,
        minute=0,
        id="combined_morning_brief",
        replace_existing=True,
    )

    # Sunday at 09:00 — stale-contact reach-out section
    scheduler.add_job(
        append_reachout_to_brief,
        trigger="cron",
        day_of_week="sun",
        hour=9,
        minute=0,
        id="reachout",
        replace_existing=True,
    )

    scheduler.add_job(
        send_midday_reading_prompt,
        trigger="cron",
        hour=mid_h,
        minute=mid_m,
        id="ross_midday_reading",
        replace_existing=True,
    )
    scheduler.add_job(
        send_evening_reading_checkin,
        trigger="cron",
        hour=eve_h,
        minute=eve_m,
        id="ross_evening_reading",
        replace_existing=True,
    )
    scheduler.add_job(
        send_practice_nudge,
        trigger="cron",
        hour=prac_h,
        minute=prac_m,
        id="ross_practice_nudge",
        replace_existing=True,
    )
    scheduler.add_job(
        write_weekly_review,
        trigger="cron",
        day_of_week="sun",
        hour=18,
        minute=0,
        id="ross_weekly_review",
        replace_existing=True,
    )
    scheduler.add_job(
        send_stale_in_progress_ping,
        trigger="cron",
        hour=10,
        minute=30,
        id="ross_stale_in_progress",
        replace_existing=True,
    )
    scheduler.add_job(
        send_discovery_suggestions,
        trigger="cron",
        day_of_week="sun",
        hour=11,
        minute=0,
        id="ross_discovery",
        replace_existing=True,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info("Scheduler started — combined brief, reachout, and Ross proactive jobs enabled")


def stop_scheduler() -> None:
    global _scheduler
    if not _scheduler:
        return
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _scheduler = None
