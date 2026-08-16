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
        CORS_ALLOWED_ORIGINS="http://localhost:5173,http://localhost:5174",
        POSTGRES_DB="comparison",
        POSTGRES_PASSWORD="secret",
        SERVER_PORT=28080,
    )

    assert settings.server_port == 28080
    assert settings.postgres_db == "comparison"
    assert settings.postgres_password.get_secret_value() == "secret"
    assert settings.allowed_origins == (
        "http://localhost:5173",
        "http://localhost:5174",
    )
