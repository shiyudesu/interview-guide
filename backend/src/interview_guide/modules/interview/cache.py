from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import TypeVar

from redis.asyncio import Redis

from interview_guide.common.errors import BusinessException, ErrorCode

CREATE_LOCK_PREFIX = "interview:v2:create:"
CREATE_RESULT_PREFIX = "interview:v2:create:result:"
TURN_RESULT_PREFIX = "interview:v2:turn:result:"
RESULT_TTL_SECONDS = 24 * 60 * 60
CREATE_LOCK_WAIT_SECONDS = 185
CREATE_LOCK_LEASE_SECONDS = 600
LOCK_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""

T = TypeVar("T")


class InterviewSessionCache:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get_create_result(self, request_id: str) -> str | None:
        value = await self._redis.get(f"{CREATE_RESULT_PREFIX}{request_id}")
        return str(value) if value is not None else None

    async def set_create_result(self, request_id: str, session_id: str) -> None:
        await self._redis.set(
            f"{CREATE_RESULT_PREFIX}{request_id}",
            session_id,
            ex=RESULT_TTL_SECONDS,
        )

    async def get_turn_result(self, session_id: str, request_id: str) -> str | None:
        value = await self._redis.get(f"{TURN_RESULT_PREFIX}{session_id}:{request_id}")
        return str(value) if value is not None else None

    async def set_turn_result(
        self,
        session_id: str,
        request_id: str,
        turn_id: str,
    ) -> None:
        await self._redis.set(
            f"{TURN_RESULT_PREFIX}{session_id}:{request_id}",
            turn_id,
            ex=RESULT_TTL_SECONDS,
        )

    async def execute_create_locked(
        self,
        request_id: str,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        return await self._execute_locked(
            f"{CREATE_LOCK_PREFIX}{request_id}",
            CREATE_LOCK_WAIT_SECONDS,
            CREATE_LOCK_LEASE_SECONDS,
            operation,
        )

    async def _execute_locked(
        self,
        key: str,
        wait_seconds: float,
        lease_seconds: int,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        owner = uuid.uuid4().hex
        deadline = time.monotonic() + wait_seconds
        acquired = False
        while time.monotonic() < deadline:
            acquired = bool(
                await self._redis.set(
                    key,
                    owner,
                    nx=True,
                    ex=lease_seconds,
                )
            )
            if acquired:
                break
            await asyncio.sleep(0.1)
        if not acquired:
            raise BusinessException(ErrorCode.INTERNAL_ERROR, f"获取锁失败: {key}")
        try:
            return await operation()
        finally:
            await self._redis.eval(LOCK_RELEASE_SCRIPT, 1, key, owner)
