from __future__ import annotations

import re

import httpx

from interview_guide.common.ai.encryption import ApiKeyEncryption
from interview_guide.common.ai.providers import (
    LlmProviderRegistry,
    ProviderRepository,
    provider_now,
)
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import LlmProviderConfig
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.modules.llm_provider.models import (
    CreateProviderRequest,
    DefaultProviderRequest,
    ProviderResponse,
    ProviderTestResult,
    UpdateProviderRequest,
)


def mask_api_key(api_key: str | None) -> str:
    if api_key is None or len(api_key) <= 6:
        return "***"
    return f"{api_key[:3]}***{api_key[-3:]}"


class LlmProviderService:
    def __init__(
        self,
        repository: ProviderRepository,
        registry: LlmProviderRegistry,
        encryption: ApiKeyEncryption,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._encryption = encryption
        self._settings = settings

    async def list(self) -> list[ProviderResponse]:
        setting = await self._repository.global_setting()
        providers = await self._repository.all_providers()
        return [
            self._response(
                provider,
                setting.default_chat_provider_id,
                setting.default_embedding_provider_id,
            )
            for provider in providers
        ]

    async def get(self, provider_id: str) -> ProviderResponse:
        setting = await self._repository.global_setting()
        provider = await self._repository.get_provider(provider_id)
        return self._response(
            provider,
            setting.default_chat_provider_id,
            setting.default_embedding_provider_id,
        )

    async def defaults(self) -> DefaultProviderRequest:
        setting = await self._repository.global_setting()
        return DefaultProviderRequest(
            default_provider=setting.default_chat_provider_id,
            default_embedding_provider=setting.default_embedding_provider_id,
        )

    async def update_default_chat(
        self,
        request: DefaultProviderRequest,
    ) -> None:
        provider_id = self._required(
            request.default_provider,
            "defaultProvider 不能为空",
        )
        await self._repository.update_default_chat(
            provider_id,
            provider_now(self._settings),
        )
        await self._registry.publish_change()

    async def update_default_embedding(
        self,
        request: DefaultProviderRequest,
    ) -> None:
        provider_id = self._required(
            request.default_embedding_provider,
            "defaultEmbeddingProvider 不能为空",
        )
        await self._repository.update_default_embedding(
            provider_id,
            provider_now(self._settings),
        )
        await self._registry.publish_change()

    async def reload(self) -> None:
        await self._registry.reload()

    async def create(self, request: CreateProviderRequest) -> None:
        provider_id = self._required(request.id, "id 不能为空")
        base_url = self._required(request.base_url, "baseUrl 不能为空")
        model = self._required(request.model, "model 不能为空")
        api_key = self._required(request.api_key, "apiKey 不能为空")
        embedding_model = self._trim(request.embedding_model)
        dimensions = self._dimensions(request.embedding_dimensions)
        supports_embedding = (
            request.supports_embedding
            if request.supports_embedding is not None
            else embedding_model is not None
        )
        self._validate_embedding(
            provider_id,
            supports_embedding,
            embedding_model,
            dimensions,
        )
        encrypted = self._encryption.encrypt(api_key)
        timestamp = provider_now(self._settings)
        await self._repository.create_provider(
            LlmProviderConfig(
                id=provider_id,
                api_key_ciphertext=encrypted.ciphertext,
                api_key_nonce=encrypted.nonce,
                base_url=base_url,
                builtin=False,
                created_at=timestamp,
                embedding_dimensions=dimensions,
                embedding_model=embedding_model,
                enabled=True,
                model=model,
                supports_embedding=supports_embedding,
                temperature=request.temperature,
                updated_at=timestamp,
            )
        )
        await self._registry.publish_change()

    async def update(
        self,
        provider_id: str,
        request: UpdateProviderRequest,
    ) -> None:
        provider = await self._repository.get_provider(provider_id)
        values: dict[str, object] = {}
        for field_name, value, message in (
            ("base_url", request.base_url, "baseUrl 不能为空字符串"),
            ("model", request.model, "model 不能为空字符串"),
            ("api_key", request.api_key, "apiKey 不能为空字符串"),
        ):
            trimmed = self._trim(value)
            if value is not None and trimmed is None:
                raise BusinessException(ErrorCode.BAD_REQUEST, message)
            if trimmed is not None and field_name != "api_key":
                values[field_name] = trimmed
        embedding_model = provider.embedding_model
        dimensions = provider.embedding_dimensions or self._settings.ai_embedding_dimensions
        supports_embedding = provider.supports_embedding
        if request.embedding_model is not None:
            embedding_model = self._trim(request.embedding_model)
            values["embedding_model"] = embedding_model
        if request.embedding_dimensions is not None:
            dimensions = self._dimensions(request.embedding_dimensions)
            values["embedding_dimensions"] = dimensions
        if request.supports_embedding is not None:
            supports_embedding = request.supports_embedding
            values["supports_embedding"] = supports_embedding
        self._validate_embedding(
            provider_id,
            supports_embedding,
            embedding_model,
            dimensions,
        )
        if request.temperature is not None:
            values["temperature"] = request.temperature
        trimmed_api_key = self._trim(request.api_key)
        if trimmed_api_key is not None:
            encrypted = self._encryption.encrypt(trimmed_api_key)
            values["api_key_nonce"] = encrypted.nonce
            values["api_key_ciphertext"] = encrypted.ciphertext
        values["updated_at"] = provider_now(self._settings)
        await self._repository.update_provider(provider_id, values)
        await self._registry.publish_change()

    async def delete(self, provider_id: str) -> None:
        await self._repository.delete_provider(provider_id)
        await self._registry.publish_change()

    async def test(self, provider_id: str) -> ProviderTestResult:
        provider = await self._repository.get_provider(provider_id)
        api_key = self._encryption.decrypt(
            provider.api_key_nonce,
            provider.api_key_ciphertext,
        )
        candidates = connectivity_test_urls(provider.base_url)
        last_failure = "Unknown error"
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5, read=10, write=10, pool=5),
            follow_redirects=False,
        ) as client:
            for url in candidates:
                try:
                    response = await client.post(
                        url,
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={
                            "model": provider.model,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "Reply with OK only.",
                                }
                            ],
                            "max_tokens": 1,
                        },
                    )
                    response.raise_for_status()
                    return ProviderTestResult(
                        success=True,
                        message="连接成功",
                        model=provider.model,
                    )
                except httpx.HTTPStatusError as error:
                    body = abbreviate(error.response.text)
                    last_failure = f"HTTP {error.response.status_code} on {url}, body={body}"
                except Exception as error:
                    last_failure = f"{type(error).__name__} on {url}: {error}"
        return ProviderTestResult(
            success=False,
            message=f"连接失败: {last_failure}",
            model=provider.model,
        )

    def _response(
        self,
        provider: LlmProviderConfig,
        default_chat: str,
        default_embedding: str,
    ) -> ProviderResponse:
        api_key = self._encryption.decrypt(
            provider.api_key_nonce,
            provider.api_key_ciphertext,
        )
        return ProviderResponse(
            id=provider.id,
            base_url=provider.base_url,
            masked_api_key=mask_api_key(api_key),
            model=provider.model,
            embedding_model=provider.embedding_model,
            embedding_dimensions=(
                provider.embedding_dimensions or self._settings.ai_embedding_dimensions
            ),
            supports_embedding=provider.supports_embedding,
            temperature=provider.temperature,
            default_chat_provider=provider.id == default_chat,
            default_embedding_provider=provider.id == default_embedding,
        )

    @staticmethod
    def _required(value: str | None, message: str) -> str:
        if value is None or not value.strip():
            raise BusinessException(ErrorCode.BAD_REQUEST, message)
        return value.strip()

    @staticmethod
    def _trim(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _dimensions(self, value: int | None) -> int:
        return value if value is not None and value > 0 else self._settings.ai_embedding_dimensions

    @staticmethod
    def _validate_embedding(
        provider_id: str,
        supports_embedding: bool,
        embedding_model: str | None,
        dimensions: int,
    ) -> None:
        if not supports_embedding:
            return
        if embedding_model is None:
            raise BusinessException(
                ErrorCode.BAD_REQUEST,
                "支持 Embedding 的 Provider 必须填写 embeddingModel",
            )
        normalized = embedding_model.lower()
        if normalized.startswith(("glm-", "deepseek", "kimi", "moonshot", "qwen", "ernie")):
            recommendations = {
                "dashscope": "text-embedding-v3",
                "glm": "embedding-3",
            }
            recommendation = recommendations.get(provider_id.lower())
            suffix = (
                f"，推荐填写 {recommendation}"
                if recommendation is not None
                else "，请填写该厂商真实的 Embedding 模型名"
            )
            raise BusinessException(
                ErrorCode.BAD_REQUEST,
                f"Embedding Model 不能填写聊天模型 '{embedding_model}'{suffix}",
            )
        if dimensions <= 0:
            raise BusinessException(ErrorCode.BAD_REQUEST, "向量维度必须为正整数")


def abbreviate(value: str | None) -> str:
    if value is None or not value.strip():
        return "[no body]"
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized if len(normalized) <= 200 else f"{normalized[:200]}..."


def connectivity_test_urls(base_url: str) -> list[str]:
    normalized = base_url.strip().rstrip("/")
    candidates = [f"{normalized}/chat/completions"]
    if not re.search(r"/v\d+[A-Za-z0-9]*$", normalized):
        candidates.append(f"{normalized}/v1/chat/completions")
    return list(dict.fromkeys(candidates))
