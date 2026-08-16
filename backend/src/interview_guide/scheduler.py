from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from interview_guide.common.config.settings import get_settings
from interview_guide.common.logging.config import configure_logging
from interview_guide.process import install_shutdown_handlers

logger = logging.getLogger(__name__)


async def run_scheduler(stop_event: asyncio.Event | None = None) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    resolved_stop_event = stop_event or asyncio.Event()
    if stop_event is None:
        install_shutdown_handlers(resolved_stop_event)
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.start()
    logger.info("scheduler started jobCount=0")
    try:
        await resolved_stop_event.wait()
    finally:
        scheduler.shutdown(wait=True)
        logger.info("scheduler stopped")


def main() -> None:
    asyncio.run(run_scheduler())
