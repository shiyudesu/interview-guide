from __future__ import annotations

import asyncio
import logging

from interview_guide.common.config.settings import get_settings
from interview_guide.common.logging.config import configure_logging
from interview_guide.common.redis import RedisConnection
from interview_guide.common.redis.streams import (
    STREAM_DEFINITIONS,
    RedisStreamService,
)
from interview_guide.process import install_shutdown_handlers

logger = logging.getLogger(__name__)


async def run_worker(
    stop_event: asyncio.Event | None = None,
    redis_connection: RedisConnection | None = None,
) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    resolved_stop_event = stop_event or asyncio.Event()
    if stop_event is None:
        install_shutdown_handlers(resolved_stop_event)
    connection = redis_connection or RedisConnection(settings)
    owns_connection = redis_connection is None
    try:
        await connection.start()
        streams = RedisStreamService(connection.client)
        for definition in STREAM_DEFINITIONS:
            await streams.ensure_group(definition)
        logger.info("worker started streamCount=%s", len(STREAM_DEFINITIONS))
        await resolved_stop_event.wait()
    finally:
        if owns_connection:
            await connection.close()
        logger.info("worker stopped")


def main() -> None:
    asyncio.run(run_worker())
