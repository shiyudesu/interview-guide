from __future__ import annotations

import os

import pytest
from redis.asyncio import Redis

from interview_guide.common.redis.streams import INTERVIEW_EVALUATE
from interview_guide.modules.voice_interview.evaluation import VoiceEvaluateStreamHandler

REDIS_URL = os.getenv("TEST_REDIS_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(REDIS_URL is None, reason="TEST_REDIS_URL is required"),
]


class FakeVoiceRepository:
    async def find_session(self, session_id: int):
        return object()

    async def core_session_public_id(self, session_id: int) -> str | None:
        return f"core-{session_id}"

    async def core_evaluate_status(self, session_id: int) -> str | None:
        del session_id
        return "PENDING"


class RedisStreams:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def add(self, key: str, fields: dict[str, str]) -> str:
        return str(await self.redis.xadd(key, fields))


class FakeStatus:
    async def update_evaluate_status(
        self,
        session_id: int,
        status: str,
        error: str | None,
    ) -> None:
        del session_id, status, error


@pytest.mark.asyncio
async def test_legacy_voice_stream_forwards_to_real_unified_stream() -> None:
    assert REDIS_URL is not None
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await redis.delete(INTERVIEW_EVALUATE.key)
    try:
        handler = VoiceEvaluateStreamHandler(
            FakeVoiceRepository(),  # type: ignore[arg-type]
            RedisStreams(redis),  # type: ignore[arg-type]
            FakeStatus(),
        )
        await handler.process(type("Payload", (), {"session_id": 7})())
        rows = await redis.xrange(INTERVIEW_EVALUATE.key)
        assert rows[0][1]["sessionId"] == "core-7"
    finally:
        await redis.delete(INTERVIEW_EVALUATE.key)
        await redis.aclose()
