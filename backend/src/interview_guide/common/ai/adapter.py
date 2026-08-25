from __future__ import annotations

import base64
import json
import re
import struct
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from interview_guide.common.ai.outbound import ProviderOutboundPolicy
from interview_guide.common.errors import BusinessException, ErrorCode

TRAILING_VERSION = re.compile(r"/v\d+[A-Za-z0-9]*$")


def resolve_versioned_base_url(base_url: str) -> str:
    stripped = base_url.strip().rstrip("/")
    return stripped if TRAILING_VERSION.search(stripped) else f"{stripped}/v1"


@dataclass(frozen=True)
class ProviderConfig:
    provider_id: str
    base_url: str
    api_key: str
    model: str
    embedding_model: str | None = None
    embedding_dimensions: int = 1024
    supports_embedding: bool = False
    temperature: float | None = None


@dataclass(frozen=True)
class ChatResult:
    content: str | None
    message: dict[str, Any]
    usage: dict[str, Any] | None
    raw: dict[str, Any]


class LlmAdapter:
    def __init__(
        self,
        outbound_policy: ProviderOutboundPolicy,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._outbound_policy = outbound_policy
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            transport=outbound_policy.guarded_http_transport(
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
            ),
            timeout=httpx.Timeout(
                connect=10,
                read=300,
                write=300,
                pool=10,
            ),
            follow_redirects=False,
            trust_env=False,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def chat(
        self,
        provider: ProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        payload = self._chat_payload(
            provider,
            messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            stream=False,
        )
        response = await self._request(
            provider,
            "chat/completions",
            payload,
        )
        document = self._json(response)
        choices = document.get("choices")
        if not isinstance(choices, list) or not choices:
            raise BusinessException(
                ErrorCode.AI_SERVICE_ERROR,
                "AI服务调用失败，请稍后重试",
            )
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise BusinessException(
                ErrorCode.AI_SERVICE_ERROR,
                "AI服务调用失败，请稍后重试",
            )
        content = message.get("content")
        return ChatResult(
            content=content if isinstance(content, str) else None,
            message=dict(message),
            usage=document.get("usage") if isinstance(document.get("usage"), dict) else None,
            raw=document,
        )

    async def stream_chat(
        self,
        provider: ProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = self._chat_payload(
            provider,
            messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            stream=True,
        )
        url = self._url(provider, "chat/completions")
        await self._outbound_policy.validate_http_url(url)
        try:
            async with self._client.stream(
                "POST",
                url,
                headers=self._headers(provider),
                json=payload,
            ) as response:
                self._raise_for_status(response)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    yield json.loads(data)
        except httpx.TimeoutException as error:
            raise BusinessException(
                ErrorCode.AI_SERVICE_TIMEOUT,
                "AI服务响应超时，请稍后重试",
            ) from error
        except httpx.RequestError as error:
            raise BusinessException(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                "AI服务暂时不可用，请稍后重试",
            ) from error

    async def embed(
        self,
        provider: ProviderConfig,
        inputs: Sequence[str],
    ) -> list[list[float]]:
        if not provider.supports_embedding or not provider.embedding_model:
            raise BusinessException(
                ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                f"Provider '{provider.provider_id}' 未配置可用的 Embedding 模型，"
                "无法执行知识库向量化",
            )
        if len(inputs) > 10:
            raise ValueError("Embedding 每批最多 10 条")
        response = await self._request(
            provider,
            "embeddings",
            {
                "model": provider.embedding_model,
                "input": list(inputs),
                "dimensions": provider.embedding_dimensions,
                "encoding_format": "base64",
            },
        )
        document = self._json(response)
        data = document.get("data")
        if not isinstance(data, list):
            raise BusinessException(
                ErrorCode.AI_SERVICE_ERROR,
                "AI服务调用失败，请稍后重试",
            )
        ordered = sorted(data, key=lambda item: int(item["index"]))
        return [self._embedding_values(item["embedding"]) for item in ordered]

    async def _request(
        self,
        provider: ProviderConfig,
        path: str,
        payload: dict[str, Any],
    ) -> httpx.Response:
        url = self._url(provider, path)
        await self._outbound_policy.validate_http_url(url)
        try:
            response = await self._client.post(
                url,
                headers=self._headers(provider),
                json=payload,
            )
        except httpx.TimeoutException as error:
            raise BusinessException(
                ErrorCode.AI_SERVICE_TIMEOUT,
                "AI服务响应超时，请稍后重试",
            ) from error
        except httpx.RequestError as error:
            raise BusinessException(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                "AI服务暂时不可用，请稍后重试",
            ) from error
        self._raise_for_status(response)
        return response

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code == 401:
            raise BusinessException(
                ErrorCode.AI_API_KEY_INVALID,
                "AI服务密钥无效，请联系管理员",
            )
        if response.status_code == 429:
            raise BusinessException(
                ErrorCode.AI_RATE_LIMIT_EXCEEDED,
                "AI服务调用过于频繁，请稍后重试",
            )
        raise BusinessException(
            ErrorCode.AI_SERVICE_ERROR,
            "AI服务调用失败，请稍后重试",
        )

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, Any]:
        try:
            document = response.json()
        except ValueError as error:
            raise BusinessException(
                ErrorCode.AI_SERVICE_ERROR,
                "AI服务调用失败，请稍后重试",
            ) from error
        if not isinstance(document, dict):
            raise BusinessException(
                ErrorCode.AI_SERVICE_ERROR,
                "AI服务调用失败，请稍后重试",
            )
        return document

    @staticmethod
    def _headers(provider: ProviderConfig) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _url(provider: ProviderConfig, path: str) -> str:
        return f"{resolve_versioned_base_url(provider.base_url)}/{path}"

    @staticmethod
    def _embedding_values(value: Any) -> list[float]:
        if isinstance(value, list):
            return [float(item) for item in value]
        if isinstance(value, str):
            raw = base64.b64decode(value, validate=True)
            if len(raw) % 4 != 0:
                raise BusinessException(
                    ErrorCode.AI_SERVICE_ERROR,
                    "AI服务调用失败，请稍后重试",
                )
            return list(struct.unpack(f"<{len(raw) // 4}f", raw))
        raise BusinessException(
            ErrorCode.AI_SERVICE_ERROR,
            "AI服务调用失败，请稍后重试",
        )

    @staticmethod
    def _chat_payload(
        provider: ProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None,
        tool_choice: str | dict[str, Any] | None,
        temperature: float | None,
        stream: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": provider.model,
            "messages": list(messages),
            "temperature": (
                temperature
                if temperature is not None
                else provider.temperature
                if provider.temperature is not None
                else 0.2
            ),
        }
        if tools is not None:
            payload["tools"] = list(tools)
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if stream:
            payload["stream"] = True
        return payload
