from __future__ import annotations

import hashlib
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from uuid import UUID

from redis.asyncio import Redis


@dataclass(frozen=True)
class AuthSession:
    session_id: str
    user_id: UUID
    role: str
    csrf_token: str
    created_at: int
    absolute_expires_at: int


@dataclass(frozen=True)
class CreatedSession:
    token: str
    session: AuthSession


class AuthSessionStore:
    def __init__(
        self,
        redis: Redis,
        *,
        idle_seconds: int,
        absolute_seconds: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._redis = redis
        self._idle_seconds = idle_seconds
        self._absolute_seconds = absolute_seconds
        self._clock = clock

    async def create(self, user_id: UUID, role: str) -> CreatedSession:
        token = secrets.token_urlsafe(32)
        session_id = session_token_hash(token)
        now = int(self._clock())
        session = AuthSession(
            session_id=session_id,
            user_id=user_id,
            role=role,
            csrf_token=secrets.token_urlsafe(32),
            created_at=now,
            absolute_expires_at=now + self._absolute_seconds,
        )
        ttl = self._ttl(session, now)
        user_key = self._user_sessions_key(user_id)
        async with self._redis.pipeline(transaction=True) as pipeline:
            pipeline.set(
                self._session_key(session_id),
                self._serialize(session),
                ex=ttl,
            )
            pipeline.sadd(user_key, session_id)
            pipeline.expire(user_key, self._absolute_seconds)
            await pipeline.execute()
        return CreatedSession(token, session)

    async def get(self, token: str) -> AuthSession | None:
        session_id = session_token_hash(token)
        raw = await self._redis.get(self._session_key(session_id))
        if raw is None:
            return None
        try:
            document = json.loads(raw)
            session = AuthSession(
                session_id=session_id,
                user_id=UUID(str(document["user_id"])),
                role=str(document["role"]),
                csrf_token=str(document["csrf_token"]),
                created_at=int(document["created_at"]),
                absolute_expires_at=int(document["absolute_expires_at"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            await self._redis.delete(self._session_key(session_id))
            return None
        now = int(self._clock())
        ttl = self._ttl(session, now)
        if ttl <= 0:
            await self.revoke(session.session_id, session.user_id)
            return None
        await self._redis.expire(self._session_key(session_id), ttl)
        return session

    async def revoke(self, session_id: str, user_id: UUID) -> None:
        async with self._redis.pipeline(transaction=True) as pipeline:
            pipeline.delete(self._session_key(session_id))
            pipeline.srem(self._user_sessions_key(user_id), session_id)
            await pipeline.execute()

    async def revoke_all(self, user_id: UUID) -> None:
        user_key = self._user_sessions_key(user_id)
        session_ids = await self._redis.smembers(user_key)
        keys = [self._session_key(str(session_id)) for session_id in session_ids]
        async with self._redis.pipeline(transaction=True) as pipeline:
            if keys:
                pipeline.delete(*keys)
            pipeline.delete(user_key)
            await pipeline.execute()

    def _ttl(self, session: AuthSession, now: int) -> int:
        return min(self._idle_seconds, session.absolute_expires_at - now)

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"auth:session:{session_id}"

    @staticmethod
    def _user_sessions_key(user_id: UUID) -> str:
        return f"auth:user-sessions:{user_id}"

    @staticmethod
    def _serialize(session: AuthSession) -> str:
        document = asdict(session)
        document["user_id"] = str(session.user_id)
        return json.dumps(document, ensure_ascii=False, separators=(",", ":"))


def session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
