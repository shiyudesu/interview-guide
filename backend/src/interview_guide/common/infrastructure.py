from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

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
from interview_guide.common.redis.rate_limit import RateLimiter
from interview_guide.common.redis.streams import RedisStreamService
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.infrastructure.file.document import create_document_parser
from interview_guide.infrastructure.storage.keys import FileKeyGenerator
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
        self.streams = RedisStreamService(self.redis.client)
        resources = Path(__file__).resolve().parents[3] / "resources"
        self.rate_limiter = RateLimiter(
            self.redis.client,
            resources / "scripts/rate_limit_single.lua",
        )
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
        prompt_boundary_uuid = (
            uuid.UUID(settings.migration_prompt_boundary_uuid)
            if settings.migration_prompt_boundary_uuid
            else None
        )
        self.prompt_sanitizer = PromptSanitizer(
            uuid_factory=(
                (lambda: prompt_boundary_uuid) if prompt_boundary_uuid is not None else uuid.uuid4
            )
        )
        self.voice_config = VoiceConfigStore(settings)
        key_generator: FileKeyGenerator | None = None
        if settings.migration_fixed_time or settings.migration_file_uuid:
            fixed_time = (
                datetime.fromisoformat(settings.migration_fixed_time)
                if settings.migration_fixed_time
                else datetime.now()
            )
            fixed_uuid = (
                uuid.UUID(settings.migration_file_uuid)
                if settings.migration_file_uuid
                else uuid.uuid4()
            )
            key_generator = FileKeyGenerator(
                now=lambda: fixed_time,
                uuid_factory=lambda: fixed_uuid,
            )
        self.storage = S3Storage(
            settings,
            self.blocking_executor,
            key_generator=key_generator,
        )
        self.document_parser = create_document_parser(
            settings,
            self.blocking_executor,
        )
        self.api_key_encryption = encryption
        self._started = False

    async def start(self) -> None:
        await self.redis.start()
        await self.rate_limiter.start()
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
