from __future__ import annotations

from pathlib import Path

from interview_guide.common.ai.adapter import LlmAdapter
from interview_guide.common.ai.encryption import (
    ApiKeyEncryption,
    resolve_configured_key,
)
from interview_guide.common.ai.outbound import ProviderOutboundPolicy
from interview_guide.common.ai.prompts import PromptSanitizer
from interview_guide.common.ai.providers import (
    ProviderRepository,
    provider_now,
)
from interview_guide.common.ai.user_providers import (
    UserLlmProviderResolver,
    UserProviderRepository,
)
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import LEGACY_OWNER_ID
from interview_guide.common.db.session import Database
from interview_guide.common.redis import RedisConnection
from interview_guide.common.redis.rate_limit import RateLimiter
from interview_guide.common.redis.streams import RedisStreamService
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.infrastructure.file.document import create_document_parser
from interview_guide.infrastructure.storage.s3 import S3Storage
from interview_guide.modules.auth.runtime import AuthRuntime
from interview_guide.modules.llm_provider.voice import VoiceConfigService


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
        self.auth_runtime = AuthRuntime(
            self.database.sessions,
            self.redis.client,
            self.rate_limiter,
            self.blocking_executor,
            settings,
        )
        encryption = ApiKeyEncryption(resolve_configured_key(settings))
        legacy_repository = ProviderRepository(self.database.sessions)
        self.legacy_provider_repository = legacy_repository
        self.provider_repository = UserProviderRepository(
            self.database.sessions,
            LEGACY_OWNER_ID,
        )
        self._settings = settings
        self.provider_outbound_policy = ProviderOutboundPolicy.from_settings(
            settings,
            self.blocking_executor,
        )
        self.provider_resolver = UserLlmProviderResolver(
            self.database.sessions,
            encryption,
            self.redis.client,
            settings,
        )
        self.provider_registry = self.provider_resolver.for_user(LEGACY_OWNER_ID)
        self.llm_adapter = LlmAdapter(self.provider_outbound_policy)
        self.prompt_sanitizer = PromptSanitizer()
        self.voice_config = VoiceConfigService(
            self.provider_repository,
            self.provider_registry,
            encryption,
            self.provider_outbound_policy,
        )
        self.storage = S3Storage(
            settings,
            self.blocking_executor,
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
        await self.legacy_provider_repository.bootstrap(
            self._settings,
            self.api_key_encryption,
            now=provider_now,
        )
        await self.provider_repository.ensure_defaults(self._settings, provider_now())
        await self.provider_resolver.start()
        self._started = True

    async def close(self) -> None:
        if self._started:
            await self.provider_resolver.close()
        await self.llm_adapter.close()
        await self.redis.close()
        await self.database.close()
        if self._owns_blocking_executor:
            await self.blocking_executor.shutdown()
