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
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.redis.rate_limit import RateLimiter
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.modules.auth.action_tokens import AuthActionTokenStore
from interview_guide.modules.auth.models import (
    ActionTokenRequest,
    EmailRequest,
    LoginRequest,
    PasswordResetConfirmRequest,
    RegisterRequest,
)
from interview_guide.modules.auth.passwords import PasswordService
from interview_guide.modules.auth.repository import AuthRepository
from interview_guide.modules.auth.service import AuthService, utc_now
from interview_guide.modules.auth.session import AuthSessionStore


class RecordingMailer:
    def __init__(self) -> None:
        self.verification_tokens: list[str] = []
        self.password_reset_tokens: list[str] = []

    async def send_email_verification(
        self,
        email: str,
        display_name: str | None,
        token: str,
    ) -> None:
        del email, display_name
        self.verification_tokens.append(token)

    async def send_password_reset(
        self,
        email: str,
        display_name: str | None,
        token: str,
    ) -> None:
        del email, display_name
        self.password_reset_tokens.append(token)


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
    mailer: RecordingMailer
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
        APP_AUTH_REGISTRATION_ENABLED=True,
        APP_AUTH_PUBLIC_URL="https://interview.example.test",
        APP_AUTH_SMTP_HOST="smtp.example.test",
        APP_AUTH_SMTP_FROM_EMAIL="noreply@example.test",
    )
    database = Database(settings)
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    executor = BlockingExecutor(max_workers=1)
    repository = AuthRepository(database.sessions)
    passwords = PasswordService(executor)
    sessions = AuthSessionStore(redis, idle_seconds=300, absolute_seconds=900)
    action_tokens = AuthActionTokenStore(
        redis,
        verification_seconds=600,
        password_reset_seconds=300,
    )
    rate_limiter = RateLimiter(redis, RESOURCES / "scripts/rate_limit_single.lua")
    await rate_limiter.start()
    mailer = RecordingMailer()
    service = AuthService(
        repository,
        passwords,
        sessions,
        action_tokens,
        mailer,  # type: ignore[arg-type]
        rate_limiter,
        settings,
    )
    resources = AuthResources(
        database,
        redis,
        executor,
        repository,
        passwords,
        sessions,
        mailer,
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


@pytest.mark.asyncio
async def test_registration_verification_and_password_reset_flow(
    auth_resources: AuthResources,
) -> None:
    email = f"registration-{uuid4()}@example.test"
    original_password = "correct horse battery staple"
    replacement_password = "replacement horse battery staple"

    registered = await auth_resources.service.register(
        RegisterRequest(email=email, password=original_password, displayName="New User"),
        client_ip="127.0.0.2",
    )
    user = await auth_resources.repository.get_user_by_email(email)
    assert user is not None
    auth_resources.user_ids.append(user.id)
    assert registered.verification_required is True
    assert user.status == "PENDING"
    assert user.email_verified_at is None
    assert len(auth_resources.mailer.verification_tokens) == 1

    with pytest.raises(BusinessException) as pending_login:
        await auth_resources.service.login(
            LoginRequest(email=email, password=original_password),
            client_ip="127.0.0.2",
        )
    assert pending_login.value.code == ErrorCode.AUTH_EMAIL_NOT_VERIFIED.code

    await auth_resources.service.confirm_email_verification(
        ActionTokenRequest(token=auth_resources.mailer.verification_tokens[-1])
    )
    authenticated = await auth_resources.service.login(
        LoginRequest(email=email, password=original_password),
        client_ip="127.0.0.2",
    )

    await auth_resources.service.request_password_reset(
        EmailRequest(email=email),
        client_ip="127.0.0.2",
    )
    assert len(auth_resources.mailer.password_reset_tokens) == 1
    await auth_resources.service.confirm_password_reset(
        PasswordResetConfirmRequest(
            token=auth_resources.mailer.password_reset_tokens[-1],
            newPassword=replacement_password,
        )
    )
    assert await auth_resources.sessions.get(authenticated.created.token) is None

    with pytest.raises(BusinessException) as old_password:
        await auth_resources.service.login(
            LoginRequest(email=email, password=original_password),
            client_ip="127.0.0.2",
        )
    assert old_password.value.code == ErrorCode.AUTH_INVALID_CREDENTIALS.code
    replacement_login = await auth_resources.service.login(
        LoginRequest(email=email, password=replacement_password),
        client_ip="127.0.0.2",
    )
    assert replacement_login.response.user.email == email
