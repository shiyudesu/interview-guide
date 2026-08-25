from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from interview_guide.common.ai.outbound import ProviderOutboundPolicy
from interview_guide.common.errors import BusinessException
from interview_guide.modules.llm_provider import service as provider_service
from interview_guide.modules.llm_provider.models import ModelDiscoveryRequest, UpdateProviderRequest
from interview_guide.modules.llm_provider.service import (
    LlmProviderService,
    abbreviate,
    classify_models,
    configured_model_first,
    connectivity_test_urls,
    fetch_remote_models,
    is_chat_model,
    looks_like_chat_model,
    mask_api_key,
    model_list_cache_key,
    model_list_urls,
    parse_model_ids,
)


class PublicResolver:
    async def resolve(self, host: str, port: int) -> tuple[str, ...]:
        del host, port
        return ("93.184.216.34",)


def outbound_policy() -> ProviderOutboundPolicy:
    return ProviderOutboundPolicy(PublicResolver())


def test_api_key_mask_is_stable() -> None:
    assert mask_api_key(None) == "未配置"
    assert mask_api_key("") == "未配置"
    assert mask_api_key("123456") == "***"
    assert mask_api_key("1234567") == "123***567"


def test_provider_connectivity_urls_use_expected_order() -> None:
    assert connectivity_test_urls("https://example.test/v1/") == [
        "https://example.test/v1/chat/completions"
    ]
    assert connectivity_test_urls("https://example.test") == [
        "https://example.test/chat/completions",
        "https://example.test/v1/chat/completions",
    ]
    assert abbreviate("  error\nbody  ") == "error body"


def test_embedding_named_qwen_model_is_not_treated_as_chat() -> None:
    assert not looks_like_chat_model("qwen3.7-text-embedding")
    assert looks_like_chat_model("qwen3.5-plus")


def test_model_list_urls_support_versioned_and_openai_compatible_roots() -> None:
    assert model_list_urls("https://example.test/v1/") == ["https://example.test/v1/models"]
    assert model_list_urls("https://api.deepseek.com") == [
        "https://api.deepseek.com/models",
        "https://api.deepseek.com/v1/models",
    ]


def test_model_ids_are_deduplicated_sorted_and_classified() -> None:
    models = parse_model_ids(
        {
            "data": [
                {"id": "qwen-plus"},
                {"id": "text-embedding-v3"},
                {"id": " qwen-plus "},
                {"missing": "ignored"},
            ]
        }
    )
    assert models == ["qwen-plus", "text-embedding-v3"]
    assert classify_models(models) == (["qwen-plus"], ["text-embedding-v3"])
    assert configured_model_first("qwen-max", models) == [
        "qwen-max",
        "qwen-plus",
        "text-embedding-v3",
    ]


def test_non_chat_modalities_are_not_offered_as_chat_models() -> None:
    assert is_chat_model("qwen3.7-max")
    assert is_chat_model("qwen3.5-omni-plus")
    assert not is_chat_model("qwen3-asr-flash-realtime")
    assert not is_chat_model("qwen3-tts-flash")
    assert not is_chat_model("qwen-image-3.0")
    assert not is_chat_model("vanchin/deepseek-ocr")


def test_model_cache_key_does_not_expose_credentials() -> None:
    cache_key = model_list_cache_key("https://example.test/v1", "top-secret")
    assert cache_key.startswith("llm:provider:models:")
    assert "top-secret" not in cache_key


@pytest.mark.asyncio
async def test_remote_model_fetch_tries_openai_v1_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.path == "/models":
            return httpx.Response(404, json={"error": "not found"})
        return httpx.Response(
            200,
            json={"data": [{"id": "model-b"}, {"id": "model-a"}]},
        )

    async_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def test_client(**kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return async_client(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        provider_service.httpx,
        "AsyncClient",
        test_client,
    )

    models, warning = await fetch_remote_models(
        "https://example.test",
        "secret",
        outbound_policy(),
    )

    assert models == ["model-a", "model-b"]
    assert warning is None
    assert [request.url.path for request in captured] == ["/models", "/v1/models"]
    assert all(request.headers["authorization"] == "Bearer secret" for request in captured)


@pytest.mark.asyncio
async def test_provider_without_api_key_uses_configured_models_without_http_request() -> None:
    repository = Mock()
    repository.get_provider = AsyncMock(
        return_value=SimpleNamespace(
            api_key_ciphertext=b"",
            api_key_nonce=b"",
            base_url="https://api.moonshot.cn/v1",
            embedding_model=None,
            model="kimi-k2.6",
        )
    )
    encryption = Mock()
    encryption.decrypt.return_value = ""
    service = LlmProviderService(
        repository,
        Mock(),
        encryption,
        Mock(),
        Mock(),
        outbound_policy(),
    )

    result = await service.discover_models(ModelDiscoveryRequest(provider_id="kimi"))
    connection = await service.test("kimi")

    assert result.chat_models == ["kimi-k2.6"]
    assert result.embedding_models == []
    assert result.source == "configured"
    assert result.warning == "Provider 未配置 API Key，无法拉取模型列表"
    assert connection.success is False
    assert connection.message == "连接失败: Provider 未配置 API Key"


@pytest.mark.asyncio
async def test_saved_key_cannot_be_sent_to_request_override_base_url() -> None:
    repository = Mock()
    repository.get_provider = AsyncMock(
        return_value=SimpleNamespace(
            api_key_ciphertext="ciphertext",
            api_key_nonce="nonce",
            base_url="https://provider.example/v1",
            embedding_model=None,
            model="model",
        )
    )
    encryption = Mock()
    service = LlmProviderService(
        repository,
        Mock(),
        encryption,
        Mock(),
        Mock(),
        outbound_policy(),
    )

    with pytest.raises(BusinessException, match="不能修改 baseUrl"):
        await service.discover_models(
            ModelDiscoveryRequest(
                provider_id="saved",
                base_url="https://attacker.example/v1",
            )
        )

    encryption.decrypt.assert_not_called()


@pytest.mark.asyncio
async def test_provider_base_url_change_requires_new_key() -> None:
    repository = Mock()
    repository.get_provider = AsyncMock(
        return_value=SimpleNamespace(
            base_url="https://provider.example/v1",
            embedding_dimensions=1024,
            embedding_model=None,
            supports_embedding=False,
        )
    )
    service = LlmProviderService(
        repository,
        Mock(),
        Mock(),
        Mock(ai_embedding_dimensions=1024),
        Mock(),
        outbound_policy(),
    )

    with pytest.raises(BusinessException, match="必须同时填写新的 apiKey"):
        await service.update(
            "saved",
            UpdateProviderRequest(base_url="https://replacement.example/v1"),
        )

    repository.update_provider.assert_not_called()
