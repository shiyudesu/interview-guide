from __future__ import annotations

from functools import lru_cache
from pathlib import Path
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
    infrastructure_startup_enabled: bool = Field(
        default=True,
        validation_alias="APP_INFRASTRUCTURE_STARTUP_ENABLED",
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
    ai_config_allow_fallback_encryption_key: bool = Field(
        default=False,
        validation_alias="APP_AI_CONFIG_ALLOW_FALLBACK_ENCRYPTION_KEY",
    )
    ai_default_provider: str = Field(
        default="dashscope",
        validation_alias="APP_AI_DEFAULT_PROVIDER",
    )
    ai_default_embedding_provider: str = Field(
        default="dashscope",
        validation_alias="APP_AI_DEFAULT_EMBEDDING_PROVIDER",
    )
    ai_embedding_dimensions: int = Field(
        default=1024,
        gt=0,
        validation_alias="APP_AI_EMBEDDING_DIMENSIONS",
    )
    ai_bailian_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="AI_BAILIAN_API_KEY",
    )
    ai_model: str = Field(default="qwen3.5-flash", validation_alias="AI_MODEL")
    ai_dashscope_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias="APP_AI_PROVIDERS_DASHSCOPE_BASE_URL",
    )
    provider_lmstudio_api_key: SecretStr = Field(
        default=SecretStr("lm-studio"),
        validation_alias="PROVIDER_LMSTUDIO_API_KEY",
    )
    provider_kimi_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="PROVIDER_KIMI_API_KEY",
    )
    provider_kimi_model: str = Field(
        default="kimi-latest",
        validation_alias="PROVIDER_KIMI_MODEL",
    )
    provider_deepseek_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="PROVIDER_DEEPSEEK_API_KEY",
    )
    provider_deepseek_model: str = Field(
        default="deepseek-v4-flash",
        validation_alias="PROVIDER_DEEPSEEK_MODEL",
    )
    provider_glm_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="PROVIDER_GLM_API_KEY",
    )
    provider_glm_model: str = Field(
        default="glm-5",
        validation_alias="PROVIDER_GLM_MODEL",
    )
    voice_config_path: Path = Field(
        default=Path("~/.interview-guide/voice-config.json"),
        validation_alias="APP_VOICE_CONFIG_PATH",
    )
    voice_asr_url: str = Field(
        default="wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
        validation_alias="APP_VOICE_INTERVIEW_QWEN_ASR_URL",
    )
    voice_asr_model: str = Field(
        default="qwen3-asr-flash-realtime",
        validation_alias="APP_VOICE_INTERVIEW_QWEN_ASR_MODEL",
    )
    voice_asr_language: str = Field(
        default="zh",
        validation_alias="APP_VOICE_INTERVIEW_QWEN_ASR_LANGUAGE",
    )
    voice_asr_format: str = Field(
        default="pcm",
        validation_alias="APP_VOICE_INTERVIEW_QWEN_ASR_FORMAT",
    )
    voice_asr_sample_rate: int = Field(
        default=16000,
        validation_alias="APP_VOICE_INTERVIEW_QWEN_ASR_SAMPLE_RATE",
    )
    voice_asr_enable_turn_detection: bool = Field(
        default=True,
        validation_alias="APP_VOICE_INTERVIEW_QWEN_ASR_ENABLE_TURN_DETECTION",
    )
    voice_asr_turn_detection_type: str = Field(
        default="server_vad",
        validation_alias="APP_VOICE_INTERVIEW_QWEN_ASR_TURN_DETECTION_TYPE",
    )
    voice_asr_turn_detection_threshold: float = Field(
        default=0,
        validation_alias="APP_VOICE_INTERVIEW_QWEN_ASR_TURN_DETECTION_THRESHOLD",
    )
    voice_asr_silence_ms: int = Field(
        default=2000,
        validation_alias="APP_VOICE_ASR_SILENCE_MS",
    )
    voice_tts_model: str = Field(
        default="qwen3-tts-flash-realtime",
        validation_alias="APP_VOICE_INTERVIEW_QWEN_TTS_MODEL",
    )
    voice_tts_voice: str = Field(
        default="Cherry",
        validation_alias="APP_VOICE_INTERVIEW_QWEN_TTS_VOICE",
    )
    voice_tts_format: str = Field(
        default="pcm",
        validation_alias="APP_VOICE_INTERVIEW_QWEN_TTS_FORMAT",
    )
    voice_tts_sample_rate: int = Field(
        default=24000,
        validation_alias="APP_VOICE_INTERVIEW_QWEN_TTS_SAMPLE_RATE",
    )
    voice_tts_mode: str = Field(
        default="commit",
        validation_alias="APP_VOICE_INTERVIEW_QWEN_TTS_MODE",
    )
    voice_tts_language_type: str = Field(
        default="Chinese",
        validation_alias="APP_VOICE_INTERVIEW_QWEN_TTS_LANGUAGE_TYPE",
    )
    voice_tts_speech_rate: float = Field(
        default=1,
        validation_alias="APP_VOICE_INTERVIEW_QWEN_TTS_SPEECH_RATE",
    )
    voice_tts_volume: int = Field(
        default=60,
        validation_alias="APP_VOICE_INTERVIEW_QWEN_TTS_VOLUME",
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
    migration_provider_nonce_hex: str | None = Field(
        default=None,
        validation_alias="MIGRATION_PROVIDER_NONCE_HEX",
    )
    migration_file_uuid: str | None = Field(
        default=None,
        validation_alias="MIGRATION_FILE_UUID",
    )

    @model_validator(mode="after")
    def validate_required_secrets(self) -> Settings:
        missing_key = (
            self.ai_config_encryption_key is None
            or not self.ai_config_encryption_key.get_secret_value().strip()
        )
        if missing_key and self.ai_config_require_encryption_key:
            raise ValueError(
                "APP_AI_CONFIG_ENCRYPTION_KEY 未配置，无法初始化 Provider API Key 加密"
            )
        if (
            missing_key
            and not self.ai_config_require_encryption_key
            and not self.ai_config_allow_fallback_encryption_key
        ):
            raise ValueError(
                "APP_AI_CONFIG_ENCRYPTION_KEY 未配置，且未显式允许 Provider API Key 开发 fallback"
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
