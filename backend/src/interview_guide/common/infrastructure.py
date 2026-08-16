from __future__ import annotations

from interview_guide.common.ai.adapter import LlmAdapter
from interview_guide.common.ai.encryption import (
    ApiKeyEncryption,
    resolve_configured_key,
)
from interview_guide.common.ai.prompts import PromptSanitizer
from interview_guide.common.ai.providers import (
    LlmProviderRegistry,
    ProviderRepository,
    provider_nonce_factory,
    provider_now,
)
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.session import Database
from interview_guide.common.redis import RedisConnection
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.infrastructure.storage.s3 import S3Storage
from interview_guide.modules.llm_provider.voice import VoiceConfigStore


class RuntimeInfrastructure:
    def __init__(
        self,
        settings: Settings,
        blocking_executor: BlockingExecutor | None = None,
    ) -> None:
        self.blocking_executor = blocking_executor or BlockingExecutor(
            settings.blocking_worker_count
        )
        self._owns_blocking_executor = blocking_executor is None
        self.database = Database(settings)
        self.redis = RedisConnection(settings)
        encryption = ApiKeyEncryption(
            resolve_configured_key(settings),
            nonce_factory=provider_nonce_factory(settings),
        )
        repository = ProviderRepository(self.database.sessions)
        self.provider_repository = repository
        self._settings = settings
        self.provider_registry = LlmProviderRegistry(
            repository,
            encryption,
            self.redis.client,
            settings,
        )
        self.llm_adapter = LlmAdapter()
        self.prompt_sanitizer = PromptSanitizer()
        self.voice_config = VoiceConfigStore(settings)
        self.storage = S3Storage(settings, self.blocking_executor)
        self.api_key_encryption = encryption
        self._started = False

    async def start(self) -> None:
        await self.redis.start()
        await self.storage.start()
        await self.provider_repository.bootstrap(
            self._settings,
            self.api_key_encryption,
            now=lambda: provider_now(self._settings),
        )
        await self.provider_registry.start()
        await self.voice_config.start()
        self._started = True

    async def close(self) -> None:
        if self._started:
            await self.provider_registry.close()
        await self.llm_adapter.close()
        await self.redis.close()
        await self.database.close()
        if self._owns_blocking_executor:
            await self.blocking_executor.shutdown()
