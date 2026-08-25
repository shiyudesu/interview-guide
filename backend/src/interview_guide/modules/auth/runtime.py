from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.config.settings import Settings
from interview_guide.common.redis.rate_limit import RateLimiter
from interview_guide.common.runtime import BlockingExecutor
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
        self.repository = AuthRepository(sessions)
        self.passwords = PasswordService(executor)
        self.sessions = AuthSessionStore(
            redis,
            idle_seconds=settings.auth_session_idle_seconds,
            absolute_seconds=settings.auth_session_absolute_seconds,
        )
        self.service = AuthService(
            self.repository,
            self.passwords,
            self.sessions,
            rate_limiter,
            settings,
        )
