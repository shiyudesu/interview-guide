from __future__ import annotations

import pytest
from pydantic import ValidationError

from interview_guide.common.config.settings import Settings


def test_encryption_key_environment_override_is_optional(tmp_path) -> None:
    key_file = tmp_path / "provider.key"
    settings = Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY=None,
        APP_AI_CONFIG_ENCRYPTION_KEY_FILE=key_file,
    )

    assert settings.ai_config_encryption_key is None
    assert settings.ai_config_encryption_key_file == key_file


def test_existing_environment_names_are_supported() -> None:
    settings = Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="test-key",
        APP_DATABASE_MAX_OVERFLOW=3,
        APP_DATABASE_POOL_SIZE=12,
        APP_PROVIDER_OUTBOUND_ALLOWED_HOSTS="lmstudio.internal, ollama.internal",
        APP_PROVIDER_OUTBOUND_ALLOWED_NETWORKS="192.168.10.0/24,10.20.0.0/16",
        CORS_ALLOWED_ORIGINS="http://localhost:5173,http://localhost:5174",
        POSTGRES_DB="comparison",
        POSTGRES_PASSWORD="secret",
        SERVER_PORT=28080,
    )

    assert settings.server_port == 28080
    assert settings.database_pool_size == 12
    assert settings.database_max_overflow == 3
    assert settings.postgres_db == "comparison"
    assert settings.postgres_password.get_secret_value() == "secret"
    assert settings.provider_outbound_allowed_host_list == (
        "lmstudio.internal",
        "ollama.internal",
    )
    assert settings.provider_outbound_allowed_network_list == (
        "192.168.10.0/24",
        "10.20.0.0/16",
    )
    assert settings.allowed_origins == (
        "http://localhost:5173",
        "http://localhost:5174",
    )


def test_database_pool_limits_reject_invalid_values() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APP_DATABASE_POOL_SIZE=0,
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APP_DATABASE_MAX_OVERFLOW=-1,
        )
