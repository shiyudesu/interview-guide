from __future__ import annotations

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
    DefaultProviderRequest,
    ProviderResponse,
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
