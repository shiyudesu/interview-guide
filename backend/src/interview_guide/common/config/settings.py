from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_environment: str = Field(default="development", validation_alias="APP_ENV")
    server_host: str = Field(default="0.0.0.0", validation_alias="SERVER_HOST")
    server_port: int = Field(default=8080, validation_alias="SERVER_PORT")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    timezone: str = Field(default="Asia/Shanghai", validation_alias="TZ")

    cors_allowed_origins: str = Field(
        default=(
            "http://localhost:5173,http://localhost:5174,http://localhost:80,"
            "http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:80"
        ),
        validation_alias="CORS_ALLOWED_ORIGINS",
    )
    multipart_max_bytes: int = Field(
        default=50 * 1024 * 1024,
        validation_alias="APP_MULTIPART_MAX_BYTES",
    )
    blocking_worker_count: int = Field(
        default=8,
        ge=1,
        validation_alias="APP_BLOCKING_WORKER_COUNT",
    )
    document_worker_count: int = Field(
        default=2,
        ge=1,
        validation_alias="APP_DOCUMENT_WORKER_COUNT",
    )
    document_conversion_timeout_seconds: float = Field(
        default=60,
        gt=0,
        validation_alias="APP_DOCUMENT_CONVERSION_TIMEOUT_SECONDS",
    )
    document_conversion_max_bytes: int = Field(
        default=100 * 1024 * 1024,
        gt=0,
        validation_alias="APP_DOCUMENT_CONVERSION_MAX_BYTES",
    )

    postgres_host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_db: str = Field(
        default="interview_guide",
        validation_alias="POSTGRES_DB",
    )
    postgres_user: str = Field(default="postgres", validation_alias="POSTGRES_USER")
    postgres_password: SecretStr = Field(
        default=SecretStr("123456"),
        validation_alias="POSTGRES_PASSWORD",
    )

    redis_host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="REDIS_PORT")
    redis_db: int = Field(default=0, ge=0, validation_alias="REDIS_DB")

    storage_endpoint: str = Field(
        default="http://localhost:9000",
        validation_alias="APP_STORAGE_ENDPOINT",
    )
    storage_access_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="APP_STORAGE_ACCESS_KEY",
    )
    storage_secret_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="APP_STORAGE_SECRET_KEY",
    )
    storage_bucket: str = Field(
        default="interview-guide",
        validation_alias="APP_STORAGE_BUCKET",
    )
    storage_region: str = Field(
        default="us-east-1",
        validation_alias="APP_STORAGE_REGION",
    )
    storage_api_call_timeout_seconds: float = Field(
        default=60,
        gt=0,
        validation_alias="APP_STORAGE_API_CALL_TIMEOUT_SECONDS",
    )
    storage_api_call_attempt_timeout_seconds: float = Field(
        default=20,
        gt=0,
        validation_alias="APP_STORAGE_API_CALL_ATTEMPT_TIMEOUT_SECONDS",
    )
    storage_auto_create_bucket: bool = Field(
        default=True,
        validation_alias="APP_STORAGE_AUTO_CREATE_BUCKET",
    )

    ai_config_encryption_key: SecretStr | None = Field(
        default=None,
        validation_alias="APP_AI_CONFIG_ENCRYPTION_KEY",
    )
    ai_config_require_encryption_key: bool = Field(
        default=True,
        validation_alias="APP_AI_CONFIG_REQUIRE_ENCRYPTION_KEY",
    )

    otel_enabled: bool = Field(default=True, validation_alias="OTEL_ENABLED")
    otel_service_name: str = Field(
        default="interview-guide-api",
        validation_alias="OTEL_SERVICE_NAME",
    )
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None,
        validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )

    migration_fixed_time: str | None = Field(
        default=None,
        validation_alias="MIGRATION_FIXED_TIME",
    )

    @model_validator(mode="after")
    def validate_required_secrets(self) -> Settings:
        if self.ai_config_require_encryption_key and (
            self.ai_config_encryption_key is None
            or not self.ai_config_encryption_key.get_secret_value().strip()
        ):
            raise ValueError(
                "APP_AI_CONFIG_ENCRYPTION_KEY 未配置，无法初始化 Provider API Key 加密"
            )
        return self

    @property
    def allowed_origins(self) -> tuple[str, ...]:
        return tuple(
            origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()
        )

    @property
    def sqlalchemy_url(self) -> str:
        password = quote_plus(self.postgres_password.get_secret_value())
        user = quote_plus(self.postgres_user)
        database = quote_plus(self.postgres_db)
        return (
            f"postgresql+psycopg://{user}:{password}@"
            f"{self.postgres_host}:{self.postgres_port}/{database}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
