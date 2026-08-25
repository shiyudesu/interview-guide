from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete

from interview_guide.common.ai.encryption import ApiKeyEncryption
from interview_guide.common.ai.outbound import ProviderOutboundPolicy
from interview_guide.common.ai.user_providers import (
    UserLlmProviderResolver,
    UserProviderRepository,
)
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import UserAccount
from interview_guide.common.db.session import Database
from interview_guide.modules.auth.repository import AuthRepository
from interview_guide.modules.auth.service import utc_now
from interview_guide.modules.llm_provider.models import CreateProviderRequest
from interview_guide.modules.llm_provider.service import LlmProviderService

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
REDIS_URL = os.getenv("TEST_REDIS_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        POSTGRES_URL is None or REDIS_URL is None,
        reason="TEST_POSTGRES_URL and TEST_REDIS_URL are required",
    ),
]


class PublicResolver:
    async def resolve(self, host: str, port: int) -> tuple[str, ...]:
        del host, port
        return ("93.184.216.34",)


@dataclass
class ProviderResources:
    database: Database
    redis: Redis
    settings: Settings
    encryption: ApiKeyEncryption
    resolver: UserLlmProviderResolver
    user_ids: list[UUID]


@pytest.fixture
async def provider_resources() -> AsyncIterator[ProviderResources]:
    assert POSTGRES_URL is not None
    assert REDIS_URL is not None
    postgres = urlsplit(POSTGRES_URL)
    redis_url = urlsplit(REDIS_URL)
    settings = Settings(
        _env_file=None,
        POSTGRES_HOST=postgres.hostname or "127.0.0.1",
        POSTGRES_PORT=postgres.port or 5432,
        POSTGRES_DB=postgres.path.removeprefix("/"),
        POSTGRES_USER=postgres.username or "postgres",
        POSTGRES_PASSWORD=postgres.password or "",
        REDIS_HOST=redis_url.hostname or "127.0.0.1",
        REDIS_PORT=redis_url.port or 6379,
        REDIS_DB=int(redis_url.path.removeprefix("/") or "0"),
    )
    database = Database(settings)
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    encryption = ApiKeyEncryption("user-provider-integration-key")
    resolver = UserLlmProviderResolver(database.sessions, encryption, redis, settings)
    resources = ProviderResources(database, redis, settings, encryption, resolver, [])
    try:
        yield resources
    finally:
        async with database.sessions() as session, session.begin():
            if resources.user_ids:
                await session.execute(
                    delete(UserAccount).where(UserAccount.id.in_(resources.user_ids))
                )
        await redis.aclose()
        await database.close()


async def create_user(resources: ProviderResources, label: str) -> UserAccount:
    repository = AuthRepository(resources.database.sessions, resources.settings)
    user = await repository.create_human_user(
        email=f"provider-{label}-{uuid4()}@example.test",
        display_name=label,
        password_hash="integration-placeholder-hash",
        role="USER",
        status="ACTIVE",
        now=utc_now(),
        email_verified=True,
    )
    resources.user_ids.append(user.id)
    return user


def provider_service(resources: ProviderResources, user_id: UUID) -> LlmProviderService:
    repository = UserProviderRepository(resources.database.sessions, user_id)
    return LlmProviderService(
        repository,
        resources.resolver.for_user(user_id),
        resources.encryption,
        resources.settings,
        resources.redis,
        ProviderOutboundPolicy(PublicResolver()),
    )


@pytest.mark.asyncio
async def test_same_alias_uses_each_users_own_api_key(
    provider_resources: ProviderResources,
) -> None:
    user_a = await create_user(provider_resources, "a")
    user_b = await create_user(provider_resources, "b")
    service_a = provider_service(provider_resources, user_a.id)
    service_b = provider_service(provider_resources, user_b.id)

    for service, api_key in ((service_a, "key-a"), (service_b, "key-b")):
        await service.create(
            CreateProviderRequest(
                id="shared-alias",
                base_url="https://provider.example/v1",
                api_key=api_key,
                model="chat-model",
            )
        )

    resolved_a = await provider_resources.resolver.for_user(user_a.id).get_chat("shared-alias")
    resolved_b = await provider_resources.resolver.for_user(user_b.id).get_chat("shared-alias")

    assert resolved_a.api_key == "key-a"
    assert resolved_b.api_key == "key-b"
    assert [item.id for item in await service_a.list()] == ["dashscope", "shared-alias"]
    assert [item.id for item in await service_b.list()] == ["dashscope", "shared-alias"]
