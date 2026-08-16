from __future__ import annotations

import asyncio
import logging

from interview_guide.common.config.settings import get_settings
from interview_guide.common.logging.config import configure_logging
from interview_guide.process import install_shutdown_handlers

logger = logging.getLogger(__name__)


async def run_worker(stop_event: asyncio.Event | None = None) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    resolved_stop_event = stop_event or asyncio.Event()
    if stop_event is None:
        install_shutdown_handlers(resolved_stop_event)
    logger.info("worker started streamCount=0")
    await resolved_stop_event.wait()
    logger.info("worker stopped")


def main() -> None:
    asyncio.run(run_worker())
