from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aiohttp import (
    ClientConnectionError,
    ClientSession,
    ClientTimeout,
    WSMsgType,
    web,
)

from model_proxy.recording import (
    JsonlRecorder,
    body_record,
    sanitize_headers,
    websocket_message_record,
)

HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


@dataclass(frozen=True)
class ProxyConfig:
    allowed_hosts: frozenset[str]
    control_token: str | None
    enable_faults: bool
    max_record_bytes: int
    record_path: Path
    upstream_connect_timeout: float


@dataclass
class Fault:
    count: int
    delay_ms: int
    mode: str
    status: int


class FaultState:
    def __init__(self) -> None:
        self._fault: Fault | None = None
        self._lock = asyncio.Lock()

    async def set(self, fault: Fault | None) -> None:
        async with self._lock:
            self._fault = fault

    async def take(self) -> Fault | None:
        async with self._lock:
            if self._fault is None or self._fault.count <= 0:
                return None
            fault = Fault(**vars(self._fault))
            self._fault.count -= 1
            if self._fault.count == 0:
                self._fault = None
            return fault


CONFIG_KEY = web.AppKey("config", ProxyConfig)
FAULTS_KEY = web.AppKey("faults", FaultState)
RECORDER_KEY = web.AppKey("recorder", JsonlRecorder)
SESSION_KEY = web.AppKey("session", ClientSession)


def target_url(
    scheme: str,
    host: str,
    tail: str,
    allowed_hosts: frozenset[str],
    query_string: str = "",
) -> str:
    allowed_schemes = {"http", "https", "ws", "wss"}
    if scheme not in allowed_schemes:
        raise web.HTTPBadRequest(text=f"Unsupported upstream scheme: {scheme}")
    hostname = host.rsplit(":", 1)[0].lower()
    if hostname not in allowed_hosts:
        raise web.HTTPForbidden(text=f"Upstream host is not allowed: {hostname}")
    path = f"/{tail}" if tail else ""
    query = f"?{query_string}" if query_string else ""
    return f"{scheme}://{host}{path}{query}"


def forwarded_headers(headers: Any) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }


def websocket_headers(headers: Any) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
        and not key.lower().startswith("sec-websocket-")
    }


def response_headers(headers: Any) -> list[tuple[str, str]]:
    return [
        (key, value)
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    ]


def request_id(request: web.Request) -> str:
    return request.headers.get("X-Request-Id") or str(uuid.uuid4())


def require_control_access(request: web.Request) -> None:
    config = request.app[CONFIG_KEY]
    if config.control_token is None:
        return
    if request.headers.get("X-Model-Proxy-Control-Token") != config.control_token:
        raise web.HTTPUnauthorized(text="Invalid model proxy control token")


async def health(request: web.Request) -> web.Response:
    return web.json_response({"status": "UP"})


async def configure_fault(request: web.Request) -> web.Response:
    require_control_access(request)
    config = request.app[CONFIG_KEY]
    if not config.enable_faults:
        raise web.HTTPForbidden(text="Fault injection is disabled")
    payload = await request.json()
    mode = payload.get("mode")
    if mode not in {"disconnect", "status", "timeout"}:
        raise web.HTTPBadRequest(text="mode must be disconnect, status, or timeout")
    fault = Fault(
        count=max(1, int(payload.get("count", 1))),
        delay_ms=max(0, int(payload.get("delayMs", 0))),
        mode=mode,
        status=int(payload.get("status", 500)),
    )
    if fault.mode == "status" and fault.status not in {429, 500, 502, 503, 504}:
        raise web.HTTPBadRequest(text="status fault must use 429 or a supported 5xx")
    await request.app[FAULTS_KEY].set(fault)
    return web.json_response({"configured": vars(fault)})


async def reset_fault(request: web.Request) -> web.Response:
    require_control_access(request)
    await request.app[FAULTS_KEY].set(None)
    return web.json_response({"reset": True})


async def apply_fault(
    request: web.Request, correlation_id: str
) -> web.StreamResponse | None:
    fault = await request.app[FAULTS_KEY].take()
    if fault is None:
        return None
    await request.app[RECORDER_KEY].write(
        {
            "correlationId": correlation_id,
            "fault": vars(fault),
            "kind": "fault-injected",
        }
    )
    if fault.delay_ms:
        await asyncio.sleep(fault.delay_ms / 1000)
    if fault.mode == "status":
        return web.json_response(
            {"error": {"message": "Injected model proxy fault"}},
            status=fault.status,
        )
    if fault.mode == "timeout":
        await asyncio.sleep(3600)
    if request.transport is not None:
        request.transport.abort()
    raise asyncio.CancelledError


async def proxy_http(request: web.Request) -> web.StreamResponse:
    config = request.app[CONFIG_KEY]
    correlation_id = request_id(request)
    injected = await apply_fault(request, correlation_id)
    if injected is not None:
        return injected
    upstream_url = target_url(
        request.match_info["scheme"],
        request.match_info["host"],
        request.match_info.get("tail", ""),
        config.allowed_hosts,
        request.query_string,
    )
    request_body = await request.read()
    started = time.monotonic()
    await request.app[RECORDER_KEY].write(
        {
            "body": body_record(
                request_body,
                request.headers.get("Content-Type"),
                config.max_record_bytes,
            ),
            "correlationId": correlation_id,
            "headers": sanitize_headers(request.headers),
            "kind": "http-request",
            "method": request.method,
            "path": request.path_qs,
            "upstream": upstream_url,
        }
    )
    session = request.app[SESSION_KEY]
    try:
        async with session.request(
            request.method,
            upstream_url,
            data=request_body,
            headers=forwarded_headers(request.headers),
            allow_redirects=False,
        ) as upstream:
            downstream = web.StreamResponse(
                status=upstream.status,
                reason=upstream.reason,
                headers=response_headers(upstream.headers),
            )
            await downstream.prepare(request)
            response_body = bytearray()
            async for chunk in upstream.content.iter_any():
                response_body.extend(chunk)
                await downstream.write(chunk)
            await downstream.write_eof()
            await request.app[RECORDER_KEY].write(
                {
                    "body": body_record(
                        bytes(response_body),
                        upstream.headers.get("Content-Type"),
                        config.max_record_bytes,
                    ),
                    "correlationId": correlation_id,
                    "durationMs": round((time.monotonic() - started) * 1000, 3),
                    "headers": sanitize_headers(upstream.headers),
                    "kind": "http-response",
                    "status": upstream.status,
                }
            )
            return downstream
    except (ClientConnectionError, TimeoutError) as error:
        await request.app[RECORDER_KEY].write(
            {
                "correlationId": correlation_id,
                "durationMs": round((time.monotonic() - started) * 1000, 3),
                "error": type(error).__name__,
                "kind": "upstream-error",
            }
        )
        raise web.HTTPBadGateway(text=f"Model proxy upstream failure: {type(error).__name__}")


async def forward_websocket_message(
    message: Any,
    destination: Any,
) -> bool:
    if message.type == WSMsgType.TEXT:
        await destination.send_str(message.data)
    elif message.type == WSMsgType.BINARY:
        await destination.send_bytes(message.data)
    elif message.type == WSMsgType.PING:
        await destination.ping(message.data)
    elif message.type == WSMsgType.PONG:
        await destination.pong(message.data)
    elif message.type in {WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR}:
        return False
    return True


async def websocket_pump(
    source: Any,
    destination: Any,
    recorder: JsonlRecorder,
    correlation_id: str,
    direction: str,
) -> None:
    async for message in source:
        await recorder.write(
            {
                "correlationId": correlation_id,
                "direction": direction,
                "kind": "websocket-message",
                "message": websocket_message_record(
                    message.data,
                    message.type.name.lower(),
                ),
            }
        )
        if not await forward_websocket_message(message, destination):
            break


async def proxy_websocket(request: web.Request) -> web.StreamResponse:
    config = request.app[CONFIG_KEY]
    correlation_id = request_id(request)
    injected = await apply_fault(request, correlation_id)
    if injected is not None:
        return injected
    upstream_url = target_url(
        request.match_info["scheme"],
        request.match_info["host"],
        request.match_info.get("tail", ""),
        config.allowed_hosts,
        request.query_string,
    )
    offered_protocols = [
        item.strip()
        for value in request.headers.getall("Sec-WebSocket-Protocol", [])
        for item in value.split(",")
        if item.strip()
    ]
    session = request.app[SESSION_KEY]
    async with session.ws_connect(
        upstream_url,
        headers=websocket_headers(request.headers),
        protocols=offered_protocols,
        autoping=False,
    ) as upstream:
        downstream_protocols = [upstream.protocol] if upstream.protocol else []
        downstream = web.WebSocketResponse(
            protocols=downstream_protocols,
            autoping=False,
        )
        await downstream.prepare(request)
        await request.app[RECORDER_KEY].write(
            {
                "correlationId": correlation_id,
                "headers": sanitize_headers(request.headers),
                "kind": "websocket-open",
                "path": request.path_qs,
                "upstream": upstream_url,
            }
        )
        tasks = {
            asyncio.create_task(
                websocket_pump(
                    downstream,
                    upstream,
                    request.app[RECORDER_KEY],
                    correlation_id,
                    "client-to-upstream",
                )
            ),
            asyncio.create_task(
                websocket_pump(
                    upstream,
                    downstream,
                    request.app[RECORDER_KEY],
                    correlation_id,
                    "upstream-to-client",
                )
            ),
        }
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*done, *pending, return_exceptions=True)
        await upstream.close()
        await downstream.close()
        await request.app[RECORDER_KEY].write(
            {
                "correlationId": correlation_id,
                "kind": "websocket-close",
            }
        )
        return downstream


async def create_session(app: web.Application) -> None:
    config = app[CONFIG_KEY]
    app[SESSION_KEY] = ClientSession(
        auto_decompress=False,
        timeout=ClientTimeout(
            total=None,
            connect=config.upstream_connect_timeout,
            sock_read=None,
        ),
    )


async def close_session(app: web.Application) -> None:
    await app[SESSION_KEY].close()


def create_app(config: ProxyConfig) -> web.Application:
    app = web.Application(client_max_size=64 * 1024 * 1024)
    app[CONFIG_KEY] = config
    app[FAULTS_KEY] = FaultState()
    app[RECORDER_KEY] = JsonlRecorder(config.record_path)
    app.on_startup.append(create_session)
    app.on_cleanup.append(close_session)
    app.router.add_get("/__control/health", health)
    app.router.add_post("/__control/fault", configure_fault)
    app.router.add_post("/__control/reset", reset_fault)
    app.router.add_route(
        "*",
        "/proxy/{scheme}/{host}/{tail:.*}",
        proxy_http,
    )
    app.router.add_get(
        "/ws/{scheme}/{host}/{tail:.*}",
        proxy_websocket,
    )
    return app
