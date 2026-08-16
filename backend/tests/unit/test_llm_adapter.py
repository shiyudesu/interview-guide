from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from interview_guide.common.ai.adapter import (
    LlmAdapter,
    ProviderConfig,
    resolve_versioned_base_url,
)
from interview_guide.common.ai.structured import (
    StructuredOutputInvoker,
    repair_unescaped_quotes,
)
from interview_guide.common.errors import BusinessException, ErrorCode


def provider() -> ProviderConfig:
    return ProviderConfig(
        provider_id="dashscope",
        base_url="https://example.test/compatible-mode",
        api_key="secret",
        model="qwen-test",
        embedding_model="embedding-test",
        embedding_dimensions=1024,
        supports_embedding=True,
    )


def test_versioned_base_url_matches_java_resolver() -> None:
    assert resolve_versioned_base_url("https://example.test") == ("https://example.test/v1")
    assert resolve_versioned_base_url("https://example.test/v1/") == ("https://example.test/v1")


@pytest.mark.asyncio
async def test_chat_tool_request_and_headers_are_explicit() -> None:
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "answer"}}],
                "usage": {"prompt_tokens": 1},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = LlmAdapter(client)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "lookup",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    result = await adapter.chat(
        provider(),
        [{"role": "user", "content": "question"}],
        tools=tools,
        tool_choice="auto",
    )

    assert result.content == "answer"
    request = captured[0]
    assert str(request.url) == ("https://example.test/compatible-mode/v1/chat/completions")
    assert request.headers["authorization"] == "Bearer secret"
    assert json.loads(request.content) == {
        "model": "qwen-test",
        "messages": [{"role": "user", "content": "question"}],
        "temperature": 0.2,
        "tools": tools,
        "tool_choice": "auto",
    }
    await client.aclose()


@pytest.mark.asyncio
async def test_http_failure_is_not_retried() -> None:
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        del request
        attempts += 1
        return httpx.Response(500, json={"error": "failed"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = LlmAdapter(client)

    with pytest.raises(BusinessException) as captured:
        await adapter.chat(
            provider(),
            [{"role": "user", "content": "question"}],
        )

    assert attempts == 1
    assert captured.value.code == 7003
    await client.aclose()


@pytest.mark.asyncio
async def test_embedding_batch_limit_and_order() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["dimensions"] == 1024
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [2, 3]},
                    {"index": 0, "embedding": [0, 1]},
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = LlmAdapter(client)

    assert await adapter.embed(provider(), ["first", "second"]) == [
        [0.0, 1.0],
        [2.0, 3.0],
    ]
    with pytest.raises(ValueError, match="最多 10 条"):
        await adapter.embed(provider(), ["x"] * 11)
    await client.aclose()


class StructuredResult(BaseModel):
    answer: str


class FakeAdapter:
    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.system_prompts: list[str] = []

    async def chat(
        self,
        provider_config: ProviderConfig,
        messages: list[dict[str, str]],
    ) -> object:
        del provider_config
        self.system_prompts.append(messages[0]["content"])
        content = self.contents.pop(0)
        return type("Result", (), {"content": content})()


@pytest.mark.asyncio
async def test_structured_output_repairs_then_retries_in_java_order() -> None:
    fake = FakeAdapter(
        [
            '{"answer":"candidate said "quoted" text"}',
        ]
    )
    invoker = StructuredOutputInvoker(fake)  # type: ignore[arg-type]

    result = await invoker.invoke(
        provider(),
        "system format",
        "user data",
        StructuredResult,
        ErrorCode.AI_SERVICE_ERROR,
        "failed: ",
    )

    assert result.answer == 'candidate said "quoted" text'
    assert "安全边界" in fake.system_prompts[0]


def test_quote_repair_matches_java_heuristic() -> None:
    assert repair_unescaped_quotes('{"value":"a "quote" b"}') == ('{"value":"a \\"quote\\" b"}')
