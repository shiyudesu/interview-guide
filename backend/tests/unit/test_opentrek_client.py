from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.opentrek import (
    OpenTrekCapability,
    OpenTrekProviderConfig,
    OpenTrekProviderRegistry,
)
from interview_guide.common.ai.outbound import ProviderOutboundPolicy
from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.infrastructure.opentrek.client import (
    OPENTREK_INTERVIEW_SKILLS,
    OpenTrekClient,
    OpenTrekSseDecoder,
    compact_opentrek_schema,
    final_json_snapshot,
    opentrek_message_metadata,
    render_opentrek_prompt,
)


class FixedResolver:
    async def resolve(self, host: str, port: int) -> tuple[str, ...]:
        del host, port
        return ("10.128.203.200",)


class StubRegistry:
    async def default_chat_alias(self) -> str:
        return "user-default"

    async def default_embedding_alias(self) -> str:
        return "embedding-default"

    async def get_chat(self, provider_id: str | None = None) -> ProviderConfig:
        raise AssertionError(provider_id)

    async def get_embedding(self, provider_id: str | None = None) -> ProviderConfig:
        return ProviderConfig(
            provider_id=provider_id or "embedding",
            base_url="https://example.com/v1",
            api_key="key",
            model="chat",
            embedding_model="embedding",
            supports_embedding=True,
        )

    async def get_voice(self, provider_id: str) -> ProviderConfig:
        return ProviderConfig(provider_id, "https://example.com/v1", "key", "voice")

    async def publish_change(self) -> int:
        return 7

    async def reload(self) -> None:
        return None


def opentrek_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "APP_OPENTREK_ENABLED": True,
        "APP_OPENTREK_APP_KEY": "protected-app-key",
        "APP_OPENTREK_WORKSPACE_CODE": "competition",
        "APP_OPENTREK_GENERAL_AGENT_CODE": "general-code",
        "APP_OPENTREK_INTERVIEWER_AGENT_CODE": "interviewer-code",
        "APP_OPENTREK_EVALUATOR_AGENT_CODE": "evaluator-code",
        "APP_OPENTREK_RAG_AGENT_CODE": "rag-code",
        "APP_PROVIDER_OUTBOUND_ALLOWED_HOSTS": "10.128.203.200",
        "APP_PROVIDER_OUTBOUND_ALLOWED_NETWORKS": "10.128.203.200/32",
    }
    values.update(overrides)
    return Settings(**values)


def policy() -> ProviderOutboundPolicy:
    return ProviderOutboundPolicy(
        FixedResolver(),
        allowed_hosts=("10.128.203.200",),
        allowed_networks=("10.128.203.200/32",),
    )


def provider(
    capability: OpenTrekCapability = OpenTrekCapability.GENERAL,
    skill_names: tuple[str, ...] = (),
) -> OpenTrekProviderConfig:
    return OpenTrekProviderConfig(
        provider_id=f"opentrek:{capability.value}",
        base_url=("http://10.128.203.200/sfm-agent-studio/sfm-api-gateway/gateway"),
        api_key="protected-app-key",
        model=f"{capability.value}-code",
        capability=capability,
        agent_version="123",
        skill_names=skill_names,
    )


def test_settings_validate_competition_and_mappings() -> None:
    settings = opentrek_settings(
        APP_COMPETITION_MODE=True,
        APP_OPENTREK_KB_MAPPINGS_JSON=json.dumps([{"fileHash": "a" * 64, "kbCode": "kb-one"}]),
    )

    assert settings.opentrek_kb_mappings == {"a" * 64: "kb-one"}

    with pytest.raises(ValueError, match=r"10\.128\.203\.200"):
        opentrek_settings(APP_OPENTREK_RUNTIME_BASE_URL="http://127.0.0.1/gateway")
    with pytest.raises(ValueError, match="SHA-256"):
        _ = opentrek_settings(
            APP_OPENTREK_KB_MAPPINGS_JSON='[{"fileHash":"bad","kbCode":"kb"}]'
        ).opentrek_kb_mappings
    with pytest.raises(ValueError, match="REGISTRATION_ENABLED"):
        opentrek_settings(
            APP_COMPETITION_MODE=True,
            APP_AUTH_REGISTRATION_ENABLED=True,
            APP_AUTH_ENABLED=True,
            APP_AUTH_COOKIE_SECURE=True,
            APP_AUTH_EMAIL_VERIFICATION_REQUIRED=True,
            APP_AUTH_PUBLIC_URL="https://example.edu",
            APP_AUTH_SMTP_HOST="smtp.example.edu",
            APP_AUTH_SMTP_FROM_EMAIL="noreply@example.edu",
        )


async def test_capability_registry_routes_chat_and_delegates_embedding() -> None:
    registry = OpenTrekProviderRegistry(
        StubRegistry(),
        opentrek_settings(APP_OPENTREK_INTERVIEWER_AGENT_VERSION="456"),
        OpenTrekCapability.INTERVIEWER,
    )

    configured = await registry.get_chat("ignored-user-provider")

    assert isinstance(configured, OpenTrekProviderConfig)
    assert configured.provider_id == "opentrek:interviewer"
    assert configured.model == "interviewer-code"
    assert configured.agent_version == "456"
    assert await registry.default_chat_alias() == "user-default"
    assert (await registry.get_embedding("selected")).provider_id == "selected"


def test_sse_decoder_supports_split_coalesced_and_crlf_frames() -> None:
    decoder = OpenTrekSseDecoder()

    events = decoder.feed('data: {"object":"message.')
    events += decoder.feed('delta","end":false}\r\n\r\ndata:{"object":"thought.delta"}\n')
    events += decoder.feed("\ndata: [DONE]\n\n")
    events += decoder.finish()

    assert events == [
        '{"object":"message.delta","end":false}',
        '{"object":"thought.delta"}',
        "[DONE]",
    ]


def test_interview_capabilities_bind_only_selected_published_skills() -> None:
    assert opentrek_message_metadata(provider(OpenTrekCapability.GENERAL)) == {
        "source": "interview-guide"
    }
    assert opentrek_message_metadata(provider(OpenTrekCapability.INTERVIEWER)) == {
        "source": "interview-guide"
    }
    metadata = opentrek_message_metadata(
        provider(
            OpenTrekCapability.INTERVIEWER,
            ("python-backend", "system-design"),
        )
    )

    assert metadata == {
        "source": "interview-guide",
        "skillList": ["python-backend", "system-design"],
    }
    assert len(OPENTREK_INTERVIEW_SKILLS) == 13
    with pytest.raises(BusinessException, match="未发布"):
        opentrek_message_metadata(provider(OpenTrekCapability.EVALUATOR, ("not-published",)))


async def test_non_stream_agent_lifecycle_and_prompt_transport(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path.endswith("/createSession"):
            return httpx.Response(200, json={"success": True, "data": {"uniqueCode": "s1"}})
        if path.endswith("/run"):
            payload = json.loads(request.content)
            assert payload["sessionId"] == "s1"
            assert payload["stream"] is False
            assert payload["delta"] is True
            assert "SYSTEM" in payload["message"]["text"]
            assert "TOOLS" in payload["message"]["text"]
            assert payload["message"]["metadata"] == {
                "source": "interview-guide",
                "skillList": ["python-backend"],
            }
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": {"value": "完成"}}],
                        },
                        "thoughts": [],
                        "error": None,
                    },
                },
            )
        if path.endswith("/deleteSession"):
            return httpx.Response(200, json={"success": True, "data": True})
        raise AssertionError(path)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gate = tmp_path / "opentrek-agent.lock"
    client = OpenTrekClient(
        opentrek_settings(APP_OPENTREK_AGENT_LOCK_FILE=str(gate)),
        policy(),
        http_client,
    )
    result = await client.chat(
        provider(OpenTrekCapability.INTERVIEWER, ("python-backend",)),
        [
            {"role": "system", "content": "规则"},
            {"role": "user", "content": "问题"},
        ],
        tools=[{"type": "function", "function": {"name": "lookup"}}],
    )
    await http_client.aclose()

    assert result.content == "完成"
    assert gate.stat().st_mode & 0o777 == 0o600
    assert [request.url.path.rsplit("/", 1)[-1] for request in requests] == [
        "createSession",
        "run",
        "deleteSession",
    ]
    assert all(
        request.headers["authorization"] == "Bearer protected-app-key" for request in requests
    )
    assert all("x-sfm-workspacecode" not in request.headers for request in requests)


async def test_stream_converts_deltas_and_cleans_session() -> None:
    calls: list[str] = []
    sse = (
        'data:{"object":"thought.delta","content":{"type":"text","data":"hidden"}}\n\n'
        'data:{"object":"message.delta","end":false,"content":'
        '[{"type":"text","text":{"value":"你"}}]}\n\n'
        'data:{"object":"message.delta","end":true,"content":'
        '[{"type":"text","text":{"value":"好"}}]}\n\n'
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        action = request.url.path.rsplit("/", 1)[-1]
        calls.append(action)
        if action == "createSession":
            return httpx.Response(200, json={"success": True, "data": {"uniqueCode": "s2"}})
        if action == "run":
            return httpx.Response(200, text=sse, headers={"Content-Type": "text/event-stream"})
        return httpx.Response(200, json={"success": True, "data": True})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenTrekClient(opentrek_settings(), policy(), http_client)
    chunks = [
        event["choices"][0]["delta"]["content"]
        async for event in client.stream_chat(provider(), [{"role": "user", "content": "hi"}])
    ]
    await http_client.aclose()

    assert chunks == ["你", "好"]
    assert calls == ["createSession", "run", "deleteSession"]


async def test_stream_closed_early_clears_then_deletes_session() -> None:
    calls: list[str] = []
    sse = (
        'data:{"object":"message.delta","end":false,"content":'
        '[{"type":"text","text":{"value":"partial"}}]}\n\n'
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        action = request.url.path.rsplit("/", 1)[-1]
        calls.append(action)
        if action == "createSession":
            return httpx.Response(200, json={"success": True, "data": {"uniqueCode": "s3"}})
        if action == "run":
            return httpx.Response(200, text=sse)
        return httpx.Response(200, json={"success": True, "data": True})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenTrekClient(opentrek_settings(), policy(), http_client)
    stream = cast(
        AsyncGenerator[dict[str, Any]],
        client.stream_chat(
            provider(),
            [{"role": "user", "content": "hi"}],
        ),
    )
    assert (await anext(stream))["choices"][0]["delta"]["content"] == "partial"
    await stream.aclose()
    await http_client.aclose()

    assert calls == ["createSession", "run", "clearSession", "deleteSession"]


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, ErrorCode.AI_API_KEY_INVALID),
        (403, ErrorCode.AI_SERVICE_ERROR),
        (429, ErrorCode.AI_RATE_LIMIT_EXCEEDED),
        (503, ErrorCode.AI_SERVICE_UNAVAILABLE),
    ],
)
async def test_http_error_mapping_does_not_expose_key(status: int, code: ErrorCode) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(status, text="protected-app-key")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenTrekClient(opentrek_settings(), policy(), http_client)
    with pytest.raises(BusinessException) as caught:
        await client.chat(provider(), [{"role": "user", "content": "hi"}])
    await http_client.aclose()

    assert caught.value.code == code.code
    assert "protected-app-key" not in str(caught.value)


def test_render_prompt_keeps_roles_and_unicode() -> None:
    prompt = render_opentrek_prompt(
        [
            {"role": "system", "content": "规则"},
            {"role": "user", "content": "问题"},
        ],
        None,
        None,
    )

    assert 'role="SYSTEM"' in prompt
    assert 'role="USER"' in prompt
    assert "规则" in prompt
    assert "问题" in prompt


def test_final_json_snapshot_keeps_only_last_cumulative_document() -> None:
    assert final_json_snapshot('{}{"questions":[]}{"questions":[{"question":"题"}]}') == (
        '{"questions":[{"question":"题"}]}'
    )
    assert final_json_snapshot("普通文本") == "普通文本"
    assert final_json_snapshot('{"single":true}') == '{"single":true}'


def test_compact_opentrek_schema_preserves_schema() -> None:
    content = (
        "prefix\nYour response should be in JSON format.\n"
        "Here is the JSON Schema instance your output must adhere to:\n"
        '```{"type":"object","properties":{"值":{"type":"string"}}}```'
    )

    compacted = compact_opentrek_schema(content)

    assert "```" not in compacted
    assert '"值":{"type":"string"}' in compacted
