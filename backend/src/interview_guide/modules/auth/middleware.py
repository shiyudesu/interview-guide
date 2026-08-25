from __future__ import annotations

import hmac
import json
from collections.abc import Awaitable, Callable
from http.cookies import CookieError, SimpleCookie

from starlette.datastructures import Headers
from starlette.types import Receive, Scope, Send

from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import ErrorCode
from interview_guide.modules.auth.runtime import AuthRuntime

AsgiApp = Callable[[Scope, Receive, Send], Awaitable[None]]
PUBLIC_PATHS = {
    "/health",
    "/info",
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/config",
    "/api/auth/email/verification/request",
    "/api/auth/email/verification/confirm",
    "/api/auth/password/reset/request",
    "/api/auth/password/reset/confirm",
}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class AuthenticationMiddleware:
    def __init__(self, app: AsgiApp, settings: Settings) -> None:
        self._app = app
        self._settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self._settings.auth_enabled or scope["type"] not in {"http", "websocket"}:
            await self._app(scope, receive, send)
            return
        path = str(scope.get("path", ""))
        method = str(scope.get("method", "GET")).upper()
        if scope["type"] == "http" and (method == "OPTIONS" or path in PUBLIC_PATHS):
            await self._app(scope, receive, send)
            return
        token = session_cookie(Headers(scope=scope), self._settings.auth_cookie_name)
        if token is None:
            await self._reject(scope, send, ErrorCode.AUTH_SESSION_INVALID)
            return
        runtime = auth_runtime(scope)
        authenticated = await runtime.service.authenticate_token(token)
        if authenticated is None:
            await self._reject(scope, send, ErrorCode.AUTH_SESSION_INVALID)
            return
        actor, session = authenticated
        state = scope.setdefault("state", {})
        state["actor"] = actor
        state["auth_session"] = session
        if scope["type"] == "http" and method not in SAFE_METHODS:
            headers = Headers(scope=scope)
            csrf_token = headers.get("x-csrf-token")
            if csrf_token is None or not hmac.compare_digest(csrf_token, session.csrf_token):
                await self._reject(scope, send, ErrorCode.AUTH_CSRF_INVALID)
                return
            if not request_origin_allowed(headers, scope, self._settings):
                await self._reject(scope, send, ErrorCode.AUTH_CSRF_INVALID)
                return
        await self._app(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, send: Send, error_code: ErrorCode) -> None:
        if scope["type"] == "websocket":
            await send(
                {
                    "type": "websocket.close",
                    "code": 4401,
                    "reason": error_code.message,
                }
            )
            return
        body = json.dumps(
            {"code": error_code.code, "detail": error_code.message},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        status = 403 if error_code is ErrorCode.AUTH_CSRF_INVALID else 401
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-length", str(len(body)).encode()),
                    (b"content-type", b"application/json"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def auth_runtime(scope: Scope) -> AuthRuntime:
    application = scope.get("app")
    if application is None:
        raise RuntimeError("ASGI application state is unavailable")
    infrastructure = application.state.infrastructure
    runtime: AuthRuntime = infrastructure.auth_runtime
    return runtime


def session_cookie(headers: Headers, cookie_name: str) -> str | None:
    raw_cookie = headers.get("cookie")
    if raw_cookie is None:
        return None
    cookies = SimpleCookie()
    try:
        cookies.load(raw_cookie)
    except CookieError:
        return None
    value = cookies.get(cookie_name)
    return value.value if value is not None and value.value else None


def request_origin_allowed(headers: Headers, scope: Scope, settings: Settings) -> bool:
    origin = headers.get("origin")
    if origin is None:
        return False
    allowed = set(settings.allowed_origins)
    forwarded_host = headers.get("x-forwarded-host") or headers.get("host")
    forwarded_proto = headers.get("x-forwarded-proto") or str(scope.get("scheme", "http"))
    if forwarded_host:
        allowed.add(f"{forwarded_proto}://{forwarded_host}")
    return origin in allowed
