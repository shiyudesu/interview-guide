from __future__ import annotations

import asyncio
import os
from datetime import datetime
from urllib.parse import urlsplit

import pytest
from redis.asyncio import Redis

from interview_guide.common.ai.encryption import ApiKeyEncryption
from interview_guide.common.ai.providers import (
    LlmProviderRegistry,
    ProviderRepository,
)
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.session import Database

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
REDIS_URL = os.getenv("TEST_REDIS_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        POSTGRES_URL is None or REDIS_URL is None,
        reason="TEST_POSTGRES_URL and TEST_REDIS_URL are required",
    ),
]


def settings_from_environment() -> Settings:
    assert POSTGRES_URL is not None
    assert REDIS_URL is not None
    postgres = urlsplit(POSTGRES_URL)
    redis = urlsplit(REDIS_URL)
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="comparison-provider-encryption-key",
        POSTGRES_HOST=postgres.hostname or "127.0.0.1",
        POSTGRES_PORT=postgres.port or 5432,
        POSTGRES_DB=postgres.path.removeprefix("/"),
        POSTGRES_USER=postgres.username or "postgres",
        POSTGRES_PASSWORD=postgres.password or "",
        REDIS_HOST=redis.hostname or "127.0.0.1",
        REDIS_PORT=redis.port or 6379,
        REDIS_DB=int(redis.path.removeprefix("/") or "0"),
    )


@pytest.mark.asyncio
async def test_bootstrap_registry_and_cross_process_version_reload() -> None:
    assert REDIS_URL is not None
    settings = settings_from_environment()
    database = Database(settings)
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    repository = ProviderRepository(database.sessions)
    await repository.clear_for_tests()
    await redis.flushdb()
    nonces = iter(
        [
            bytes.fromhex("000102030405060708090a0b"),
            bytes.fromhex("0c0d0e0f1011121314151617"),
        ]
    )
    encryption = ApiKeyEncryption(
        "comparison-provider-encryption-key",
        nonce_factory=lambda size: next(nonces),
    )
    await repository.bootstrap(
        settings,
        encryption,
        now=lambda: datetime(2026, 8, 16, 8, 0),
    )
    encrypted = encryption.encrypt("comparison-placeholder-key")
    await repository.update_provider(
        "dashscope",
        {
            "api_key_ciphertext": encrypted.ciphertext,
            "api_key_nonce": encrypted.nonce,
        },
    )

    first = LlmProviderRegistry(repository, encryption, redis, settings)
    second = LlmProviderRegistry(repository, encryption, redis, settings)
    await first.start()
    await second.start()
    try:
        assert (await first.get_chat()).provider_id == "dashscope"
        assert (await first.get_embedding()).embedding_dimensions == 1024
        voice_config = await repository.voice_config()
        assert voice_config.asr_provider_id == "dashscope"
        assert voice_config.tts_provider_id == "dashscope"
        assert (await first.get_voice("dashscope")).api_key == "comparison-placeholder-key"

        await repository.update_model("dashscope", "qwen-updated")
        assert await first.publish_change() == 1
        await asyncio.sleep(0.05)

        assert (await first.get_chat("dashscope")).model == "qwen-updated"
        assert (await second.get_chat("dashscope")).model == "qwen-updated"
    finally:
        await first.close()
        await second.close()
        await repository.clear_for_tests()
        restore_nonces = iter(
            [
                bytes.fromhex("000102030405060708090a0b"),
            ]
        )
        await repository.bootstrap(
            settings,
            ApiKeyEncryption(
                "comparison-provider-encryption-key",
                nonce_factory=lambda size: next(restore_nonces),
            ),
            now=lambda: datetime(2026, 8, 16, 8, 0),
        )
        await redis.flushdb()
        await redis.aclose()
        await database.close()
