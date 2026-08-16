from __future__ import annotations

from interview_guide.common.ai.encryption import (
    ApiKeyEncryption,
    resolve_configured_key,
)
from interview_guide.common.ai.providers import (
    LlmProviderRegistry,
    ProviderRepository,
    provider_nonce_factory,
    provider_now,
)
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.session import Database
from interview_guide.common.redis import RedisConnection


class RuntimeInfrastructure:
    def __init__(self, settings: Settings) -> None:
        self.database = Database(settings)
        self.redis = RedisConnection(settings)
        encryption = ApiKeyEncryption(
            resolve_configured_key(settings),
            nonce_factory=provider_nonce_factory(settings),
        )
        repository = ProviderRepository(self.database.sessions)
        self._repository = repository
        self._settings = settings
        self.provider_registry = LlmProviderRegistry(
            repository,
            encryption,
            self.redis.client,
            settings,
        )
        self._encryption = encryption
        self._started = False

    async def start(self) -> None:
        await self.redis.start()
        await self._repository.bootstrap(
            self._settings,
            self._encryption,
            now=lambda: provider_now(self._settings),
        )
        await self.provider_registry.start()
        self._started = True

    async def close(self) -> None:
        if self._started:
            await self.provider_registry.close()
        await self.redis.close()
        await self.database.close()
