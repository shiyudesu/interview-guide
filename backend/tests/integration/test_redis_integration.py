from __future__ import annotations

import asyncio
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from redis.asyncio import Redis

from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException
from interview_guide.common.redis.client import RedisConnection
from interview_guide.common.redis.rate_limit import (
    RateLimitDimension,
    RateLimiter,
    RateLimitRule,
)
from interview_guide.common.redis.streams import (
    RESUME_ANALYZE,
    STREAM_DEFINITIONS,
    RedisStreamService,
)
from interview_guide.worker import run_worker

REDIS_URL = os.getenv("TEST_REDIS_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(REDIS_URL is None, reason="TEST_REDIS_URL is not configured"),
]


@pytest.fixture
async def redis_client() -> Redis:
    assert REDIS_URL is not None
    client = Redis.from_url(REDIS_URL, decode_responses=True)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest.mark.asyncio
async def test_stream_read_pending_reclaim_and_ack(redis_client: Redis) -> None:
    streams = RedisStreamService(redis_client)
    await streams.ensure_group(RESUME_ANALYZE)
    message_id = await streams.add(
        RESUME_ANALYZE.key,
        {"resumeId": "7", "content": "fixed", "retryCount": "0"},
        message_id="1-0",
    )

    first = await streams.read_batch(
        RESUME_ANALYZE,
        "analyze-consumer-first",
        block_ms=10,
        pending_idle_ms=60_000,
    )
    assert message_id == "1-0"
    assert [message.message_id for message in first] == ["1-0"]

    await asyncio.sleep(0.02)
    reclaimed = await streams.read_batch(
        RESUME_ANALYZE,
        "analyze-consumer-second",
        block_ms=10,
        pending_idle_ms=10,
    )
    assert [message.message_id for message in reclaimed] == ["1-0"]
    assert await streams.ack(RESUME_ANALYZE, "1-0") == 1

    pending = await redis_client.xpending(RESUME_ANALYZE.key, RESUME_ANALYZE.group)
    assert pending["pending"] == 0


@pytest.mark.asyncio
async def test_rate_limit_lua_is_atomic_and_sets_ttl(redis_client: Redis) -> None:
    script = Path(__file__).resolve().parents[2] / "resources/scripts/rate_limit_single.lua"
    limiter = RateLimiter(redis_client, script)
    await limiter.start()
    rules = (
        RateLimitRule(RateLimitDimension.GLOBAL, count=1, interval_ms=1000),
        RateLimitRule(RateLimitDimension.IP, count=1, interval_ms=1000),
    )

    await limiter.check(
        scope="knowledge-base:query",
        rules=rules,
        client_ip="127.0.0.1",
        now_ms=1_000,
        request_id="fixed-request-1",
    )
    with pytest.raises(BusinessException) as captured:
        await limiter.check(
            scope="knowledge-base:query",
            rules=rules,
            client_ip="127.0.0.1",
            now_ms=1_001,
            request_id="fixed-request-2",
        )

    assert captured.value.code == 8001
    global_value_key = "ratelimit:{knowledge-base:query}:global:value"
    assert await redis_client.get(global_value_key) == "0"
    ttl = await redis_client.ttl(global_value_key)
    assert ttl in {1, 2}


@pytest.mark.asyncio
async def test_worker_creates_all_stream_groups(redis_client: Redis) -> None:
    assert REDIS_URL is not None
    parsed_url = urlsplit(REDIS_URL)
    settings = Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="integration-key",
        REDIS_HOST=parsed_url.hostname or "127.0.0.1",
        REDIS_PORT=parsed_url.port or 6379,
        REDIS_DB=int(parsed_url.path.removeprefix("/") or "0"),
    )
    connection = RedisConnection(settings)
    stop_event = asyncio.Event()
    stop_event.set()

    await run_worker(stop_event, connection)

    for definition in STREAM_DEFINITIONS:
        groups = await redis_client.xinfo_groups(definition.key)
        assert [group["name"] for group in groups] == [definition.group]
    await connection.close()
