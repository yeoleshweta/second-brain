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

    scheduler = AsyncIOScheduler()

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

    scheduler.start()
    _scheduler = scheduler
    logger.info("Scheduler started — combined_brief @ 06:00, reachout @ Sun 09:00")


def stop_scheduler() -> None:
    global _scheduler
    if not _scheduler:
        return
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _scheduler = None
