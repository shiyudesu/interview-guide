from __future__ import annotations

import pytest
from pydantic import ValidationError

from interview_guide.common.config.settings import Settings


def test_missing_required_encryption_key_fails_startup() -> None:
    with pytest.raises(ValidationError, match="APP_AI_CONFIG_ENCRYPTION_KEY"):
        Settings(
            _env_file=None,
            APP_AI_CONFIG_ENCRYPTION_KEY=None,
            APP_AI_CONFIG_REQUIRE_ENCRYPTION_KEY=True,
        )


def test_existing_environment_names_are_supported() -> None:
    settings = Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="test-key",
        APP_DATABASE_MAX_OVERFLOW=3,
        APP_DATABASE_POOL_SIZE=12,
        CORS_ALLOWED_ORIGINS="http://localhost:5173,http://localhost:5174",
        POSTGRES_DB="comparison",
        POSTGRES_PASSWORD="secret",
        SERVER_PORT=28080,
    )

    assert settings.server_port == 28080
    assert settings.ai_model == "qwen3.7-max"
    assert settings.ai_embedding_model == "qwen3.7-text-embedding"
    assert settings.database_pool_size == 12
    assert settings.database_max_overflow == 3
    assert settings.postgres_db == "comparison"
    assert settings.postgres_password.get_secret_value() == "secret"
    assert settings.allowed_origins == (
        "http://localhost:5173",
        "http://localhost:5174",
    )


def test_database_pool_limits_reject_invalid_values() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APP_AI_CONFIG_ENCRYPTION_KEY="test-key",
            APP_DATABASE_POOL_SIZE=0,
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APP_AI_CONFIG_ENCRYPTION_KEY="test-key",
            APP_DATABASE_MAX_OVERFLOW=-1,
        )
