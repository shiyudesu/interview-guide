from __future__ import annotations

from redis.asyncio import Redis

from interview_guide.common.config.settings import Settings


class RedisConnection:
    def __init__(self, settings: Settings) -> None:
        self.client = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )

    async def start(self) -> None:
        await self.client.ping()

    async def close(self) -> None:
        await self.client.aclose()
