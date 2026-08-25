from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import ErrorCode
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.modules.auth.api import session_response
from interview_guide.modules.auth.domain import Actor, UserRole
from interview_guide.modules.auth.middleware import AuthenticationMiddleware
from interview_guide.modules.auth.models import (
    AuthSessionResponse,
    UserResponse,
    normalized_email,
    validate_password_length,
)
from interview_guide.modules.auth.passwords import PasswordService
from interview_guide.modules.auth.service import AuthenticatedSession
from interview_guide.modules.auth.session import AuthSession, AuthSessionStore, CreatedSession

USER_ID = UUID("11111111-1111-1111-1111-111111111111")


class FakeAuthService:
    def __init__(self) -> None:
        self.session = AuthSession(
            session_id="session-hash",
            user_id=USER_ID,
            role="ADMIN",
            csrf_token="csrf-token",
            created_at=1,
            absolute_expires_at=9999999999,
        )

    async def authenticate_token(self, token: str):
        if token != "valid-token":
            return None
        return (
            Actor(
                user_id=USER_ID,
                role=UserRole.ADMIN,
                session_id=self.session.session_id,
                csrf_token=self.session.csrf_token,
            ),
            self.session,
        )


def auth_app() -> FastAPI:
    settings = Settings(
        _env_file=None,
        APP_AUTH_ENABLED=True,
        APP_AUTH_COOKIE_SECURE=True,
        CORS_ALLOWED_ORIGINS="https://interview.example.test",
    )
    app = FastAPI()
    app.state.infrastructure = SimpleNamespace(
        auth_runtime=SimpleNamespace(service=FakeAuthService())
    )
    app.add_middleware(AuthenticationMiddleware, settings=settings)

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/private")
    async def private_get() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/private")
    async def private_post() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_email_and_password_validation_use_unicode_character_semantics() -> None:
    assert normalized_email(" User@Example.COM ") == "user@example.com"
    with pytest.raises(ValueError, match="邮箱格式无效"):
        normalized_email("invalid")
    validate_password_length("密码安全长度十二个字符以上")
    with pytest.raises(ValueError, match="至少需要 12"):
        validate_password_length("too-short")


def test_authentication_middleware_defaults_to_deny() -> None:
    with TestClient(auth_app(), base_url="https://interview.example.test") as client:
        assert client.get("/health").status_code == 200
        denied = client.get("/api/private")
        assert denied.status_code == 401
        assert denied.json() == {
            "code": ErrorCode.AUTH_SESSION_INVALID.code,
            "detail": ErrorCode.AUTH_SESSION_INVALID.message,
        }


def test_authenticated_mutation_requires_csrf_and_same_origin() -> None:
    app = auth_app()
    with TestClient(app, base_url="https://interview.example.test") as client:
        client.cookies.set("interview_guide_session", "valid-token")
        assert client.get("/api/private").status_code == 200
        assert client.post("/api/private").status_code == 403
        wrong_origin = client.post(
            "/api/private",
            headers={
                "Origin": "https://attacker.example",
                "X-CSRF-Token": "csrf-token",
            },
        )
        assert wrong_origin.status_code == 403
        allowed = client.post(
            "/api/private",
            headers={
                "Origin": "https://interview.example.test",
                "X-CSRF-Token": "csrf-token",
            },
        )
        assert allowed.status_code == 200


@pytest.mark.parametrize(
    "path",
    ("/api/auth/login", "/api/auth/register", "/api/auth/config"),
)
def test_login_and_registration_paths_are_public(path: str) -> None:
    app = auth_app()

    @app.post(path)
    async def public_auth() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app, base_url="https://interview.example.test") as client:
        assert client.post(path).status_code == 200


class FakePipeline:
    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis
        self._operations: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    async def __aenter__(self) -> FakePipeline:
        return self

    async def __aexit__(self, *arguments: object) -> None:
        del arguments

    def set(self, *arguments: object, **keywords: object) -> None:
        self._operations.append(("set", arguments, keywords))

    def sadd(self, *arguments: object) -> None:
        self._operations.append(("sadd", arguments, {}))

    def expire(self, *arguments: object) -> None:
        self._operations.append(("expire", arguments, {}))

    def delete(self, *arguments: object) -> None:
        self._operations.append(("delete", arguments, {}))

    def srem(self, *arguments: object) -> None:
        self._operations.append(("srem", arguments, {}))

    async def execute(self) -> None:
        for name, arguments, keywords in self._operations:
            if name == "set":
                assert len(arguments) == 2
                await self._redis.set(
                    arguments[0],
                    arguments[1],
                    ex=keywords["ex"],
                )
            else:
                await getattr(self._redis, name)(*arguments)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}

    def pipeline(self, *, transaction: bool) -> FakePipeline:
        assert transaction
        return FakePipeline(self)

    async def set(self, key: object, value: object, *, ex: object) -> None:
        assert int(str(ex)) > 0
        self.values[str(key)] = str(value)

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def expire(self, key: object, ttl: object) -> None:
        del key
        assert int(str(ttl)) > 0

    async def delete(self, *keys: object) -> None:
        for key in keys:
            self.values.pop(str(key), None)
            self.sets.pop(str(key), None)

    async def sadd(self, key: object, value: object) -> None:
        self.sets.setdefault(str(key), set()).add(str(value))

    async def srem(self, key: object, value: object) -> None:
        self.sets.setdefault(str(key), set()).discard(str(value))

    async def smembers(self, key: str) -> set[str]:
        return set(self.sets.get(key, set()))


@pytest.mark.asyncio
async def test_password_service_hashes_with_argon2id() -> None:
    executor = BlockingExecutor(max_workers=1)
    passwords = PasswordService(executor)
    try:
        password_hash = await passwords.hash("correct horse battery staple")
        assert password_hash.startswith("$argon2id$")
        assert await passwords.verify(password_hash, "correct horse battery staple")
        assert not await passwords.verify(password_hash, "wrong password")
    finally:
        await executor.shutdown()


@pytest.mark.asyncio
async def test_session_store_creates_touches_and_revokes_server_session() -> None:
    redis = FakeRedis()
    clock = iter((1000.0, 1001.0))
    store = AuthSessionStore(
        redis,  # type: ignore[arg-type]
        idle_seconds=300,
        absolute_seconds=900,
        clock=lambda: next(clock),
    )

    created = await store.create(USER_ID, "ADMIN")
    loaded = await store.get(created.token)

    assert loaded is not None
    assert loaded.user_id == USER_ID
    assert loaded.csrf_token == created.session.csrf_token
    await store.revoke_all(USER_ID)
    assert await store.get(created.token) is None


def test_login_response_sets_hardened_cookie_and_no_store() -> None:
    settings = Settings(
        _env_file=None,
        APP_AUTH_COOKIE_SECURE=True,
        APP_AUTH_SESSION_ABSOLUTE_SECONDS=900,
    )
    user = UserResponse(
        id=USER_ID,
        email="admin@example.com",
        display_name="Admin",
        role="ADMIN",
        status="ACTIVE",
        created_at=datetime(2026, 8, 25),
    )
    session = AuthSession(
        session_id="hash",
        user_id=USER_ID,
        role="ADMIN",
        csrf_token="csrf",
        created_at=1,
        absolute_expires_at=901,
    )
    response = session_response(
        AuthenticatedSession(
            response=AuthSessionResponse(user=user, csrf_token="csrf"),
            created=CreatedSession("raw-token", session),
        ),
        settings,
    )

    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert response.headers["cache-control"] == "no-store"
