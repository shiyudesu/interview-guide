from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.datastructures import Headers
from starlette.types import Message, Receive, Scope, Send

from interview_guide.common.logging.config import bind_request_id, reset_request_id
from interview_guide.common.metrics import ApplicationMetrics

AsgiApp = Callable[[Scope, Receive, Send], Awaitable[None]]
logger = logging.getLogger(__name__)


def request_log_level(status_code: int, duration_seconds: float) -> int:
    if status_code >= 500:
        return logging.WARNING
    if status_code >= 400 or duration_seconds >= 1:
        return logging.INFO
    return logging.DEBUG


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
            logger.log(
                request_log_level(status_code, duration),
                "request completed method=%s path=%s status=%s durationMs=%.3f",
                method,
                path_template,
                status_code,
                duration * 1000,
            )
            reset_request_id(token)


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
            {"code": 400, "detail": "文件大小超过限制"},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"content-type", b"application/json"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
