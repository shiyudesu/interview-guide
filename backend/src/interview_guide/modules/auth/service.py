from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import UserAccount
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.redis.rate_limit import (
    RateLimitDimension,
    RateLimiter,
    RateLimitRule,
)
from interview_guide.modules.auth.domain import Actor, UserRole
from interview_guide.modules.auth.models import (
    AuthSessionResponse,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from interview_guide.modules.auth.passwords import PasswordService
from interview_guide.modules.auth.repository import AuthRepository
from interview_guide.modules.auth.session import AuthSession, AuthSessionStore, CreatedSession


@dataclass(frozen=True)
class AuthenticatedSession:
    response: AuthSessionResponse
    created: CreatedSession


class AuthService:
    def __init__(
        self,
        repository: AuthRepository,
        passwords: PasswordService,
        sessions: AuthSessionStore,
        rate_limiter: RateLimiter,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._passwords = passwords
        self._sessions = sessions
        self._rate_limiter = rate_limiter
        self._settings = settings

    async def register(
        self,
        request: RegisterRequest,
        *,
        client_ip: str,
    ) -> AuthenticatedSession:
        if not self._settings.auth_registration_enabled:
            raise BusinessException(ErrorCode.AUTH_REGISTRATION_DISABLED)
        await self._rate_limiter.check(
            scope="auth.register",
            rules=(
                RateLimitRule(
                    RateLimitDimension.IP,
                    float(self._settings.auth_registration_ip_limit_per_hour),
                    interval_ms=60 * 60 * 1000,
                ),
            ),
            client_ip=client_ip,
            now_ms=int(time.time() * 1000),
        )
        password_hash = await self._passwords.hash(request.password)
        now = utc_now()
        user = await self._repository.create_human_user(
            email=request.email,
            display_name=request.display_name,
            password_hash=password_hash,
            role=UserRole.USER.value,
            status="ACTIVE",
            now=now,
            email_verified=False,
        )
        return await self._new_authenticated_session(user)

    async def login(
        self,
        request: LoginRequest,
        *,
        client_ip: str,
    ) -> AuthenticatedSession:
        account_key = hashlib.sha256(request.email.encode()).hexdigest()
        await self._rate_limiter.check(
            scope="auth.login",
            rules=(
                RateLimitRule(
                    RateLimitDimension.IP,
                    float(self._settings.auth_login_ip_limit_per_minute),
                    interval_ms=60 * 1000,
                ),
                RateLimitRule(
                    RateLimitDimension.USER,
                    float(self._settings.auth_login_account_limit_per_minute),
                    interval_ms=60 * 1000,
                ),
            ),
            client_ip=client_ip,
            user_id=account_key,
            now_ms=int(time.time() * 1000),
        )
        record = await self._repository.find_login(request.email)
        if record is None:
            await self._passwords.verify_dummy(request.password)
            raise BusinessException(ErrorCode.AUTH_INVALID_CREDENTIALS)
        verified = await self._passwords.verify(record.credential.password_hash, request.password)
        if not verified:
            raise BusinessException(ErrorCode.AUTH_INVALID_CREDENTIALS)
        if record.user.status != "ACTIVE" or record.user.kind != "HUMAN":
            raise BusinessException(ErrorCode.USER_DISABLED)
        if self._passwords.needs_rehash(record.credential.password_hash):
            rehashed = await self._passwords.hash(request.password)
            await self._repository.rehash_password(record.user.id, rehashed, utc_now())
        return await self._new_authenticated_session(record.user)

    async def current_session(
        self,
        actor: Actor,
        session: AuthSession,
    ) -> AuthSessionResponse:
        user = await self._required_active_user(actor.user_id)
        return AuthSessionResponse(
            user=user_response(user),
            csrf_token=session.csrf_token,
        )

    async def change_password(
        self,
        actor: Actor,
        request: ChangePasswordRequest,
    ) -> None:
        user = await self._required_active_user(actor.user_id)
        record = await self._repository.find_login(user.email)
        if record is None or not await self._passwords.verify(
            record.credential.password_hash,
            request.current_password,
        ):
            raise BusinessException(ErrorCode.AUTH_INVALID_CREDENTIALS)
        password_hash = await self._passwords.hash(request.new_password)
        await self._repository.update_password(actor.user_id, password_hash, utc_now())
        await self._sessions.revoke_all(actor.user_id)

    async def logout(self, actor: Actor) -> None:
        await self._sessions.revoke(actor.session_id, actor.user_id)

    async def revoke_all(self, actor: Actor) -> None:
        await self._sessions.revoke_all(actor.user_id)

    async def authenticate_token(
        self,
        token: str,
    ) -> tuple[Actor, AuthSession] | None:
        session = await self._sessions.get(token)
        if session is None:
            return None
        user = await self._repository.get_user(session.user_id)
        if user is None or user.status != "ACTIVE" or user.kind != "HUMAN":
            await self._sessions.revoke(session.session_id, session.user_id)
            return None
        try:
            role = UserRole(user.role)
        except ValueError:
            await self._sessions.revoke(session.session_id, session.user_id)
            return None
        return (
            Actor(
                user_id=user.id,
                role=role,
                session_id=session.session_id,
                csrf_token=session.csrf_token,
            ),
            session,
        )

    async def _new_authenticated_session(self, user: UserAccount) -> AuthenticatedSession:
        created = await self._sessions.create(user.id, user.role)
        return AuthenticatedSession(
            response=AuthSessionResponse(
                user=user_response(user),
                csrf_token=created.session.csrf_token,
            ),
            created=created,
        )

    async def _required_active_user(self, user_id: UUID) -> UserAccount:
        user = await self._repository.get_user(user_id)
        if user is None or user.status != "ACTIVE" or user.kind != "HUMAN":
            raise BusinessException(ErrorCode.AUTH_SESSION_INVALID)
        return user


def user_response(user: UserAccount) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
    )


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
