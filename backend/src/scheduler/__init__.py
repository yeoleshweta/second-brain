"""Application scheduler setup."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from src.agents.knowledge import build_daily_brief

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        build_daily_brief,
        trigger="cron",
        hour=6,
        minute=0,
        id="knowledge_daily_brief",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("Scheduler started with job: knowledge_daily_brief @ 06:00")


def stop_scheduler() -> None:
    global _scheduler
    if not _scheduler:
        return
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _scheduler = None
