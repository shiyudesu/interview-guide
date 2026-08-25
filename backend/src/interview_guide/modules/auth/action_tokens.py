from __future__ import annotations

import hashlib
import secrets
from uuid import UUID

from redis.asyncio import Redis


class AuthActionTokenStore:
    def __init__(
        self,
        redis: Redis,
        *,
        verification_seconds: int,
        password_reset_seconds: int,
    ) -> None:
        self._redis = redis
        self._verification_seconds = verification_seconds
        self._password_reset_seconds = password_reset_seconds

    async def create_email_verification(self, user_id: UUID) -> str:
        return await self._create("email-verify", user_id, self._verification_seconds)

    async def consume_email_verification(self, token: str) -> UUID | None:
        return await self._consume("email-verify", token)

    async def create_password_reset(self, user_id: UUID) -> str:
        return await self._create("password-reset", user_id, self._password_reset_seconds)

    async def consume_password_reset(self, token: str) -> UUID | None:
        return await self._consume("password-reset", token)

    async def _create(self, purpose: str, user_id: UUID, ttl: int) -> str:
        token = secrets.token_urlsafe(32)
        await self._redis.set(self._key(purpose, token), str(user_id), ex=ttl)
        return token

    async def _consume(self, purpose: str, token: str) -> UUID | None:
        if not token or len(token) > 256:
            return None
        raw = await self._redis.getdel(self._key(purpose, token))
        if raw is None:
            return None
        try:
            return UUID(str(raw))
        except ValueError:
            return None

    @staticmethod
    def _key(purpose: str, token: str) -> str:
        digest = hashlib.sha256(token.encode()).hexdigest()
        return f"auth:{purpose}:{digest}"
