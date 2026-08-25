from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.config.settings import Settings
from interview_guide.common.redis.rate_limit import RateLimiter
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.modules.auth.action_tokens import AuthActionTokenStore
from interview_guide.modules.auth.mailer import AuthMailer
from interview_guide.modules.auth.passwords import PasswordService
from interview_guide.modules.auth.repository import AuthRepository
from interview_guide.modules.auth.service import AuthService
from interview_guide.modules.auth.session import AuthSessionStore


class AuthRuntime:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        redis: Redis,
        rate_limiter: RateLimiter,
        executor: BlockingExecutor,
        settings: Settings,
    ) -> None:
        self.repository = AuthRepository(sessions, settings)
        self.passwords = PasswordService(executor)
        self.sessions = AuthSessionStore(
            redis,
            idle_seconds=settings.auth_session_idle_seconds,
            absolute_seconds=settings.auth_session_absolute_seconds,
        )
        self.action_tokens = AuthActionTokenStore(
            redis,
            verification_seconds=settings.auth_email_verification_seconds,
            password_reset_seconds=settings.auth_password_reset_seconds,
        )
        self.mailer = AuthMailer(settings, executor)
        self.service = AuthService(
            self.repository,
            self.passwords,
            self.sessions,
            self.action_tokens,
            self.mailer,
            rate_limiter,
            settings,
        )
