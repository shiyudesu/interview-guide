from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer
from model_proxy.app import ProxyConfig, create_app, target_url
from model_proxy.recording import body_record, sanitize_headers, sanitize_json
from multidict import CIMultiDict


class RecordingTest(unittest.TestCase):
    def test_gzip_json_is_decoded_only_for_recording(self) -> None:
        raw = gzip.compress(b'{"usage":{"prompt_tokens":3,"completion_tokens":2}}')

        record = body_record(
            raw,
            "application/json",
            1024,
            "gzip",
        )

        self.assertEqual("gzip", record["contentEncoding"])
        self.assertEqual(
            {"usage": {"prompt_tokens": 3, "completion_tokens": 2}},
            record["json"],
        )
        self.assertEqual(len(raw), record["bytes"])

    def test_secrets_are_redacted_but_model_payload_is_preserved(self) -> None:
        sanitized = sanitize_json(
            {
                "api_key": "secret",
                "messages": [{"role": "user", "content": "fixed prompt"}],
                "model": "qwen-test",
            }
        )

        self.assertTrue(sanitized["api_key"].startswith("<redacted:sha256:"))
        self.assertEqual("fixed prompt", sanitized["messages"][0]["content"])
        self.assertEqual("qwen-test", sanitized["model"])

    def test_target_url_rejects_hosts_outside_allowlist(self) -> None:
        with self.assertRaises(web.HTTPForbidden):
            target_url("https", "example.com", "v1/models", frozenset({"localhost"}))

    def test_authorization_header_is_redacted(self) -> None:
        sanitized = sanitize_headers(
            CIMultiDict(
                {
                    "Authorization": "Bearer secret",
                    "Content-Type": "application/json",
                }
            )
        )

        self.assertTrue(sanitized["authorization"][0].startswith("<redacted:sha256:"))
        self.assertEqual(["application/json"], sanitized["content-type"])


class ProxyIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.record_path = Path(self.temporary_directory.name) / "records.jsonl"

        async def echo_http(request: web.Request) -> web.Response:
            payload = await request.json()
            return web.json_response(
                {"model": payload["model"], "messages": payload["messages"]},
                headers={"X-Upstream": "echo"},
            )

        async def echo_websocket(request: web.Request) -> web.WebSocketResponse:
            websocket = web.WebSocketResponse()
            await websocket.prepare(request)
            async for message in websocket:
                if message.type.name == "TEXT":
                    await websocket.send_str(message.data)
            return websocket

        upstream_app = web.Application()
        upstream_app.router.add_post("/v1/chat/completions", echo_http)
        upstream_app.router.add_get("/realtime", echo_websocket)
        self.upstream = TestServer(upstream_app)
        await self.upstream.start_server()

        proxy_app = create_app(
            ProxyConfig(
                allowed_hosts=frozenset({"127.0.0.1"}),
                control_token=None,
                enable_faults=True,
                max_record_bytes=1024 * 1024,
                record_path=self.record_path,
                upstream_connect_timeout=5,
            )
        )
        self.proxy = TestServer(proxy_app)
        await self.proxy.start_server()
        self.session = ClientSession()

    async def asyncTearDown(self) -> None:
        await self.session.close()
        await self.proxy.close()
        await self.upstream.close()
        self.temporary_directory.cleanup()

    def proxy_url(self, prefix: str, tail: str) -> str:
        upstream_port = self.upstream.port
        return f"{self.proxy.make_url(prefix)}/http/127.0.0.1:{upstream_port}/{tail}"

    async def test_http_response_is_forwarded_without_body_changes(self) -> None:
        payload = {
            "messages": [{"content": "fixed prompt", "role": "user"}],
            "model": "qwen-test",
        }
        async with self.session.post(
            self.proxy_url("/proxy", "v1/chat/completions"),
            json=payload,
            headers={"Authorization": "Bearer secret"},
        ) as response:
            body = await response.read()

        self.assertEqual(200, response.status)
        self.assertEqual("echo", response.headers["X-Upstream"])
        self.assertEqual(
            {"messages": payload["messages"], "model": "qwen-test"},
            json.loads(body),
        )
        records = [
            json.loads(line) for line in self.record_path.read_text(encoding="utf-8").splitlines()
        ]
        request_record = next(item for item in records if item["kind"] == "http-request")
        self.assertTrue(
            request_record["headers"]["authorization"][0].startswith("<redacted:sha256:")
        )
        self.assertEqual(
            "fixed prompt",
            request_record["body"]["json"]["messages"][0]["content"],
        )

    async def test_status_fault_is_explicit_and_consumed_once(self) -> None:
        async with self.session.post(
            self.proxy.make_url("/__control/fault"),
            json={"count": 1, "mode": "status", "status": 429},
        ) as control_response:
            self.assertEqual(200, control_response.status)

        async with self.session.post(
            self.proxy_url("/proxy", "v1/chat/completions"),
            json={"messages": [], "model": "qwen-test"},
        ) as fault_response:
            self.assertEqual(429, fault_response.status)

        async with self.session.post(
            self.proxy_url("/proxy", "v1/chat/completions"),
            json={"messages": [], "model": "qwen-test"},
        ) as normal_response:
            self.assertEqual(200, normal_response.status)

    async def test_websocket_messages_are_forwarded(self) -> None:
        upstream_port = self.upstream.port
        url = f"{self.proxy.make_url('/ws')}/ws/127.0.0.1:{upstream_port}/realtime"
        async with self.session.ws_connect(url) as websocket:
            await websocket.send_json({"type": "session.update"})
            message = await websocket.receive_json()

        self.assertEqual({"type": "session.update"}, message)
        records = [
            json.loads(line) for line in self.record_path.read_text(encoding="utf-8").splitlines()
        ]
        directions = {item["direction"] for item in records if item["kind"] == "websocket-message"}
        self.assertEqual(
            {"client-to-upstream", "upstream-to-client"},
            directions,
        )


if __name__ == "__main__":
    unittest.main()
