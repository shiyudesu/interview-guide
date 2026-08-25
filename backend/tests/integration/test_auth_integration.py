from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete

from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import UserAccount
from interview_guide.common.db.session import Database
from interview_guide.common.redis.rate_limit import RateLimiter
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.modules.auth.models import LoginRequest
from interview_guide.modules.auth.passwords import PasswordService
from interview_guide.modules.auth.repository import AuthRepository
from interview_guide.modules.auth.service import AuthService, utc_now
from interview_guide.modules.auth.session import AuthSessionStore

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
REDIS_URL = os.getenv("TEST_REDIS_URL")
RESOURCES = Path(__file__).resolve().parents[2] / "resources"
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        POSTGRES_URL is None or REDIS_URL is None,
        reason="TEST_POSTGRES_URL and TEST_REDIS_URL are required",
    ),
]


@dataclass
class AuthResources:
    database: Database
    redis: Redis
    executor: BlockingExecutor
    repository: AuthRepository
    passwords: PasswordService
    sessions: AuthSessionStore
    service: AuthService
    user_ids: list[UUID]


@pytest.fixture
async def auth_resources() -> AsyncIterator[AuthResources]:
    assert POSTGRES_URL is not None
    assert REDIS_URL is not None
    postgres = urlsplit(POSTGRES_URL)
    redis_url = urlsplit(REDIS_URL)
    settings = Settings(
        _env_file=None,
        POSTGRES_HOST=postgres.hostname or "127.0.0.1",
        POSTGRES_PORT=postgres.port or 5432,
        POSTGRES_DB=postgres.path.removeprefix("/"),
        POSTGRES_USER=postgres.username or "postgres",
        POSTGRES_PASSWORD=postgres.password or "",
        REDIS_HOST=redis_url.hostname or "127.0.0.1",
        REDIS_PORT=redis_url.port or 6379,
        REDIS_DB=int(redis_url.path.removeprefix("/") or "0"),
        APP_AUTH_ENABLED=True,
        APP_AUTH_REGISTRATION_ENABLED=False,
    )
    database = Database(settings)
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    executor = BlockingExecutor(max_workers=1)
    repository = AuthRepository(database.sessions)
    passwords = PasswordService(executor)
    sessions = AuthSessionStore(redis, idle_seconds=300, absolute_seconds=900)
    rate_limiter = RateLimiter(redis, RESOURCES / "scripts/rate_limit_single.lua")
    await rate_limiter.start()
    service = AuthService(repository, passwords, sessions, rate_limiter, settings)
    resources = AuthResources(
        database,
        redis,
        executor,
        repository,
        passwords,
        sessions,
        service,
        [],
    )
    try:
        yield resources
    finally:
        for user_id in resources.user_ids:
            await sessions.revoke_all(user_id)
        async with database.sessions() as session, session.begin():
            if resources.user_ids:
                await session.execute(
                    delete(UserAccount).where(UserAccount.id.in_(resources.user_ids))
                )
        await redis.aclose()
        await database.close()
        await executor.shutdown()


@pytest.mark.asyncio
async def test_database_credentials_and_redis_session_round_trip(
    auth_resources: AuthResources,
) -> None:
    email = f"integration-{uuid4()}@example.test"
    password = "correct horse battery staple"
    password_hash = await auth_resources.passwords.hash(password)
    user = await auth_resources.repository.create_human_user(
        email=email,
        display_name="Integration User",
        password_hash=password_hash,
        role="ADMIN",
        status="ACTIVE",
        now=utc_now(),
        email_verified=True,
    )
    auth_resources.user_ids.append(user.id)

    authenticated = await auth_resources.service.login(
        LoginRequest(email=email, password=password),
        client_ip="127.0.0.1",
    )
    loaded = await auth_resources.sessions.get(authenticated.created.token)

    assert loaded is not None
    assert loaded.user_id == user.id
    assert authenticated.response.user.email == email
    await auth_resources.sessions.revoke_all(user.id)
    assert await auth_resources.sessions.get(authenticated.created.token) is None
