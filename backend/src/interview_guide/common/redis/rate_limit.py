from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from redis.asyncio import Redis
from redis.exceptions import NoScriptError

from interview_guide.common.errors import BusinessException, ErrorCode


class RateLimitDimension(StrEnum):
    GLOBAL = "GLOBAL"
    IP = "IP"
    USER = "USER"


@dataclass(frozen=True)
class RateLimitRule:
    dimension: RateLimitDimension
    count: float
    interval_ms: int = 1000


class RateLimiter:
    def __init__(self, redis: Redis, script_path: Path) -> None:
        self._redis = redis
        self._script = script_path.read_text(encoding="utf-8")
        self._script_sha: str | None = None

    async def start(self) -> None:
        self._script_sha = str(await self._redis.script_load(self._script))

    async def check(
        self,
        *,
        class_name: str,
        method_name: str,
        rules: tuple[RateLimitRule, ...],
        client_ip: str = "unknown",
        user_id: str = "anonymous",
        now_ms: int,
        request_id: str | None = None,
    ) -> None:
        if not rules:
            return
        keys = [
            self._key(
                class_name,
                method_name,
                rule.dimension,
                client_ip,
                user_id,
            )
            for rule in rules
        ]
        arguments: list[str] = [
            str(now_ms),
            request_id or str(uuid.uuid4()),
            str(len(rules)),
        ]
        for rule in rules:
            arguments.extend(
                [
                    "1",
                    str(rule.interval_ms),
                    self._format_count(rule.count),
                ]
            )
        result = await self._eval(keys, arguments)
        if result <= 0:
            raise BusinessException(
                ErrorCode.RATE_LIMIT_EXCEEDED,
                "请求过于频繁，请稍后再试",
            )

    async def _eval(self, keys: list[str], arguments: list[str]) -> int:
        if self._script_sha is None:
            await self.start()
        if self._script_sha is None:
            raise RuntimeError("Rate limit Lua script was not loaded")
        script_sha = self._script_sha
        try:
            result = await self._redis.evalsha(
                script_sha,
                len(keys),
                *keys,
                *arguments,
            )
        except NoScriptError as error:
            await self.start()
            if self._script_sha is None:
                raise RuntimeError("Rate limit Lua script was not reloaded") from error
            result = await self._redis.evalsha(
                self._script_sha,
                len(keys),
                *keys,
                *arguments,
            )
        return int(result)

    @staticmethod
    def _format_count(value: float) -> str:
        return str(math.trunc(value)) if value.is_integer() else str(value)

    @staticmethod
    def _key(
        class_name: str,
        method_name: str,
        dimension: RateLimitDimension,
        client_ip: str,
        user_id: str,
    ) -> str:
        prefix = f"ratelimit:{{{class_name}:{method_name}}}"
        if dimension is RateLimitDimension.GLOBAL:
            return f"{prefix}:global"
        if dimension is RateLimitDimension.IP:
            return f"{prefix}:ip:{client_ip}"
        return f"{prefix}:user:{user_id}"
