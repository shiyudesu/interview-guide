from __future__ import annotations

from uuid import UUID

import pytest

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.providers import static_provider_seeds
from interview_guide.common.ai.user_providers import (
    ScopedProviderRegistry,
    UserProviderDefaults,
    normalize_provider_alias,
)


def test_only_dashscope_is_seeded_without_credentials() -> None:
    seeds = static_provider_seeds()

    assert len(seeds) == 1
    assert seeds[0].provider_id == "dashscope"
    assert seeds[0].base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert seeds[0].model == "qwen3.7-max"
    assert seeds[0].embedding_model == "qwen3.7-text-embedding"
    assert seeds[0].embedding_dimensions == 1024
    assert seeds[0].supports_embedding is True


def test_provider_alias_normalization_treats_blank_and_default_as_unspecified() -> None:
    assert normalize_provider_alias(None) is None
    assert normalize_provider_alias("") is None
    assert normalize_provider_alias("   ") is None
    assert normalize_provider_alias("default") is None
    assert normalize_provider_alias(" dashscope ") == "dashscope"


@pytest.mark.asyncio
async def test_scoped_registry_uses_default_for_whitespace_provider_alias() -> None:
    user_id = UUID("11111111-1111-1111-1111-111111111111")

    class Repository:
        async def default_aliases(self) -> UserProviderDefaults:
            return UserProviderDefaults("dashscope", "dashscope")

    repository = Repository()
    repository.user_id = user_id

    class Resolver:
        async def resolve(self, resolved_user_id: UUID, alias: str) -> ProviderConfig:
            assert resolved_user_id == user_id
            assert alias == "dashscope"
            return ProviderConfig("dashscope", "https://example.test/v1", "key", "model")

    registry = ScopedProviderRegistry(  # type: ignore[arg-type]
        repository,
        Resolver(),  # type: ignore[arg-type]
    )

    assert (await registry.get_chat(" ")).provider_id == "dashscope"
