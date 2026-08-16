from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import Message, Receive, Scope, Send

from interview_guide.common.logging.config import bind_request_id, reset_request_id
from interview_guide.common.metrics import ApplicationMetrics
from interview_guide.common.result import Result

AsgiApp = Callable[[Scope, Receive, Send], Awaitable[None]]
logger = logging.getLogger(__name__)
VARY_HEADERS = (
    "Origin",
    "Access-Control-Request-Method",
    "Access-Control-Request-Headers",
)


class RequestContextMiddleware:
    def __init__(self, app: AsgiApp, metrics: ApplicationMetrics) -> None:
        self._app = app
        self._metrics = metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        request_id = headers.get("x-request-id") or str(uuid.uuid4())
        token = bind_request_id(request_id)
        started = time.monotonic()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        finally:
            duration = time.monotonic() - started
            route = scope.get("route")
            path_template = getattr(route, "path", scope.get("path", "unknown"))
            method = scope.get("method", "UNKNOWN")
            self._metrics.http_requests.labels(
                method=method,
                pathTemplate=path_template,
                status=str(status_code),
            ).inc()
            self._metrics.http_duration.labels(
                method=method,
                pathTemplate=path_template,
            ).observe(duration)
            logger.info(
                "request completed method=%s path=%s status=%s durationMs=%.3f",
                method,
                path_template,
                status_code,
                duration * 1000,
            )
            reset_request_id(token)


class CompatibilityCorsMiddleware:
    def __init__(self, app: AsgiApp, allowed_origins: tuple[str, ...]) -> None:
        self._app = app
        self._allowed_origins = set(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/"):
            await self._app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        origin = headers.get("origin")
        requested_method = headers.get("access-control-request-method")
        if scope.get("method") == "OPTIONS" and origin and requested_method:
            if origin not in self._allowed_origins:
                await self._send_plain_response(send, 403, b"Invalid CORS request")
                return
            response_headers = [
                (b"access-control-allow-origin", origin.encode("latin-1")),
                (b"access-control-allow-methods", b"GET,POST,PUT,DELETE,PATCH,OPTIONS"),
                (
                    b"access-control-allow-headers",
                    headers.get("access-control-request-headers", "").encode("latin-1"),
                ),
                (b"access-control-allow-credentials", b"true"),
            ]
            response_headers.extend((b"vary", value.encode("latin-1")) for value in VARY_HEADERS)
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": response_headers,
                }
            )
            await send({"type": "http.response.body", "body": b""})
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                mutable_headers = MutableHeaders(scope=message)
                for value in VARY_HEADERS:
                    mutable_headers.append("vary", value)
                if origin in self._allowed_origins:
                    mutable_headers["access-control-allow-origin"] = origin
                    mutable_headers["access-control-allow-credentials"] = "true"
            await send(message)

        await self._app(scope, receive, send_wrapper)

    @staticmethod
    async def _send_plain_response(send: Send, status: int, body: bytes) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"content-type", b"text/plain;charset=UTF-8"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class MultipartLimitExceeded(Exception):
    pass


class MultipartSizeLimitMiddleware:
    def __init__(self, app: AsgiApp, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        content_type = headers.get("content-type", "").lower()
        if not content_type.startswith("multipart/form-data"):
            await self._app(scope, receive, send)
            return
        content_length = headers.get("content-length")
        if content_length is not None and int(content_length) > self._max_bytes:
            await self._send_error(send)
            return
        consumed = 0

        async def limited_receive() -> Message:
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > self._max_bytes:
                    raise MultipartLimitExceeded
            return message

        try:
            await self._app(scope, limited_receive, send)
        except MultipartLimitExceeded:
            await self._send_error(send)

    @staticmethod
    async def _send_error(send: Send) -> None:
        body = json.dumps(
            Result.error(400, "文件大小超过限制").model_dump(),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"content-type", b"application/json"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
