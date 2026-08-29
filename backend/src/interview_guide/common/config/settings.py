from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus, urlsplit

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
            "http://localhost:5173,http://localhost:5174,"
            "http://127.0.0.1:5173,http://127.0.0.1:5174"
        ),
        validation_alias="CORS_ALLOWED_ORIGINS",
    )
    multipart_max_bytes: int = Field(
        default=50 * 1024 * 1024,
        validation_alias="APP_MULTIPART_MAX_BYTES",
    )
    auth_enabled: bool = Field(default=False, validation_alias="APP_AUTH_ENABLED")
    auth_registration_enabled: bool = Field(
        default=False,
        validation_alias="APP_AUTH_REGISTRATION_ENABLED",
    )
    auth_cookie_name: str = Field(
        default="interview_guide_session",
        validation_alias="APP_AUTH_COOKIE_NAME",
    )
    auth_cookie_secure: bool = Field(
        default=True,
        validation_alias="APP_AUTH_COOKIE_SECURE",
    )
    auth_session_idle_seconds: int = Field(
        default=24 * 60 * 60,
        ge=300,
        validation_alias="APP_AUTH_SESSION_IDLE_SECONDS",
    )
    auth_session_absolute_seconds: int = Field(
        default=7 * 24 * 60 * 60,
        ge=900,
        validation_alias="APP_AUTH_SESSION_ABSOLUTE_SECONDS",
    )
    auth_login_ip_limit_per_minute: int = Field(
        default=20,
        ge=1,
        validation_alias="APP_AUTH_LOGIN_IP_LIMIT_PER_MINUTE",
    )
    auth_login_account_limit_per_minute: int = Field(
        default=8,
        ge=1,
        validation_alias="APP_AUTH_LOGIN_ACCOUNT_LIMIT_PER_MINUTE",
    )
    auth_registration_ip_limit_per_hour: int = Field(
        default=5,
        ge=1,
        validation_alias="APP_AUTH_REGISTRATION_IP_LIMIT_PER_HOUR",
    )
    auth_email_verification_required: bool = Field(
        default=True,
        validation_alias="APP_AUTH_EMAIL_VERIFICATION_REQUIRED",
    )
    auth_public_url: str = Field(default="", validation_alias="APP_AUTH_PUBLIC_URL")
    auth_email_verification_seconds: int = Field(
        default=24 * 60 * 60,
        ge=300,
        validation_alias="APP_AUTH_EMAIL_VERIFICATION_SECONDS",
    )
    auth_password_reset_seconds: int = Field(
        default=60 * 60,
        ge=300,
        validation_alias="APP_AUTH_PASSWORD_RESET_SECONDS",
    )
    auth_email_request_limit_per_hour: int = Field(
        default=5,
        ge=1,
        validation_alias="APP_AUTH_EMAIL_REQUEST_LIMIT_PER_HOUR",
    )
    auth_smtp_host: str = Field(default="", validation_alias="APP_AUTH_SMTP_HOST")
    auth_smtp_port: int = Field(
        default=587,
        ge=1,
        le=65535,
        validation_alias="APP_AUTH_SMTP_PORT",
    )
    auth_smtp_username: str = Field(
        default="",
        validation_alias="APP_AUTH_SMTP_USERNAME",
    )
    auth_smtp_password: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="APP_AUTH_SMTP_PASSWORD",
    )
    auth_smtp_starttls: bool = Field(
        default=True,
        validation_alias="APP_AUTH_SMTP_STARTTLS",
    )
    auth_smtp_ssl: bool = Field(default=False, validation_alias="APP_AUTH_SMTP_SSL")
    auth_smtp_from_email: str = Field(
        default="",
        validation_alias="APP_AUTH_SMTP_FROM_EMAIL",
    )
    auth_smtp_timeout_seconds: float = Field(
        default=10,
        gt=0,
        validation_alias="APP_AUTH_SMTP_TIMEOUT_SECONDS",
    )
    blocking_worker_count: int = Field(
        default=8,
        ge=1,
        validation_alias="APP_BLOCKING_WORKER_COUNT",
    )

    @model_validator(mode="after")
    def validate_registration_delivery(self) -> Settings:
        if self.auth_smtp_ssl and self.auth_smtp_starttls:
            raise ValueError("APP_AUTH_SMTP_SSL 与 APP_AUTH_SMTP_STARTTLS 不能同时启用")
        if not self.auth_registration_enabled:
            return self
        if not self.auth_enabled:
            raise ValueError("开放注册前必须启用 APP_AUTH_ENABLED")
        if not self.auth_cookie_secure:
            raise ValueError("开放注册只允许使用 Secure Session Cookie")
        if not self.auth_email_verification_required:
            raise ValueError("开放注册前必须启用邮箱验证")
        if not self.auth_public_url.startswith("https://"):
            raise ValueError("开放注册需要配置 HTTPS 的 APP_AUTH_PUBLIC_URL")
        if not self.auth_smtp_host or not self.auth_smtp_from_email:
            raise ValueError("开放注册需要配置 SMTP 主机和发件邮箱")
        return self

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
    database_pool_size: int = Field(
        default=10,
        ge=1,
        validation_alias="APP_DATABASE_POOL_SIZE",
    )
    database_max_overflow: int = Field(
        default=0,
        ge=0,
        validation_alias="APP_DATABASE_MAX_OVERFLOW",
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
    ai_config_encryption_key_file: Path = Field(
        default=Path.home() / ".local" / "share" / "interview-guide" / "provider-encryption.key",
        validation_alias="APP_AI_CONFIG_ENCRYPTION_KEY_FILE",
    )
    ai_embedding_dimensions: int = Field(
        default=1024,
        gt=0,
        validation_alias="APP_AI_EMBEDDING_DIMENSIONS",
    )
    provider_outbound_allowed_hosts: str = Field(
        default="",
        validation_alias="APP_PROVIDER_OUTBOUND_ALLOWED_HOSTS",
    )
    provider_outbound_allowed_networks: str = Field(
        default="",
        validation_alias="APP_PROVIDER_OUTBOUND_ALLOWED_NETWORKS",
    )
    competition_mode: bool = Field(
        default=False,
        validation_alias="APP_COMPETITION_MODE",
    )
    opentrek_enabled: bool = Field(
        default=False,
        validation_alias="APP_OPENTREK_ENABLED",
    )
    opentrek_runtime_base_url: str = Field(
        default=("http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway"),
        validation_alias="APP_OPENTREK_RUNTIME_BASE_URL",
    )
    opentrek_app_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="APP_OPENTREK_APP_KEY",
    )
    opentrek_workspace_code: str = Field(
        default="",
        validation_alias="APP_OPENTREK_WORKSPACE_CODE",
    )
    opentrek_general_agent_code: str = Field(
        default="",
        validation_alias="APP_OPENTREK_GENERAL_AGENT_CODE",
    )
    opentrek_general_agent_version: str = Field(
        default="",
        validation_alias="APP_OPENTREK_GENERAL_AGENT_VERSION",
    )
    opentrek_interviewer_agent_code: str = Field(
        default="",
        validation_alias="APP_OPENTREK_INTERVIEWER_AGENT_CODE",
    )
    opentrek_interviewer_agent_version: str = Field(
        default="",
        validation_alias="APP_OPENTREK_INTERVIEWER_AGENT_VERSION",
    )
    opentrek_evaluator_agent_code: str = Field(
        default="",
        validation_alias="APP_OPENTREK_EVALUATOR_AGENT_CODE",
    )
    opentrek_evaluator_agent_version: str = Field(
        default="",
        validation_alias="APP_OPENTREK_EVALUATOR_AGENT_VERSION",
    )
    opentrek_rag_agent_code: str = Field(
        default="",
        validation_alias="APP_OPENTREK_RAG_AGENT_CODE",
    )
    opentrek_rag_agent_version: str = Field(
        default="",
        validation_alias="APP_OPENTREK_RAG_AGENT_VERSION",
    )
    opentrek_kb_mappings_json: str = Field(
        default="[]",
        validation_alias="APP_OPENTREK_KB_MAPPINGS_JSON",
    )
    opentrek_connect_timeout_seconds: float = Field(
        default=10,
        gt=0,
        validation_alias="APP_OPENTREK_CONNECT_TIMEOUT_SECONDS",
    )
    opentrek_read_timeout_seconds: float = Field(
        default=300,
        gt=0,
        validation_alias="APP_OPENTREK_READ_TIMEOUT_SECONDS",
    )
    opentrek_kb_batch_size: int = Field(
        default=10,
        ge=1,
        le=10,
        validation_alias="APP_OPENTREK_KB_BATCH_SIZE",
    )
    opentrek_agent_lock_file: str = Field(
        default="",
        validation_alias="APP_OPENTREK_AGENT_LOCK_FILE",
    )
    opentrek_agent_min_interval_seconds: float = Field(
        default=0,
        ge=0,
        le=120,
        validation_alias="APP_OPENTREK_AGENT_MIN_INTERVAL_SECONDS",
    )
    ai_rag_rewrite_enabled: bool = Field(
        default=True,
        validation_alias="APP_AI_RAG_REWRITE_ENABLED",
    )
    ai_rag_short_query_length: int = Field(
        default=4,
        validation_alias="APP_AI_RAG_SHORT_QUERY_LENGTH",
    )
    ai_rag_topk_short: int = Field(
        default=20,
        validation_alias="APP_AI_RAG_TOPK_SHORT",
    )
    ai_rag_topk_medium: int = Field(
        default=12,
        validation_alias="APP_AI_RAG_TOPK_MEDIUM",
    )
    ai_rag_topk_long: int = Field(
        default=8,
        validation_alias="APP_AI_RAG_TOPK_LONG",
    )
    ai_rag_min_score_short: float = Field(
        default=0.18,
        validation_alias="APP_AI_RAG_MIN_SCORE_SHORT",
    )
    ai_rag_min_score_default: float = Field(
        default=0.28,
        validation_alias="APP_AI_RAG_MIN_SCORE_DEFAULT",
    )
    ai_rag_history_enabled: bool = Field(
        default=True,
        validation_alias="APP_AI_RAG_HISTORY_ENABLED",
    )
    ai_rag_history_max_messages: int = Field(
        default=10,
        ge=0,
        validation_alias="APP_AI_RAG_HISTORY_MAX_MESSAGES",
    )
    interview_follow_up_count: int = Field(
        default=1,
        ge=0,
        le=2,
        validation_alias="APP_INTERVIEW_FOLLOW_UP_COUNT",
    )
    interview_turn_confidence_threshold: float = Field(
        default=0.65,
        ge=0,
        le=1,
        validation_alias="APP_INTERVIEW_TURN_CONFIDENCE_THRESHOLD",
    )
    interview_turn_decision_timeout_seconds: float = Field(
        default=20,
        gt=0,
        le=120,
        validation_alias="APP_INTERVIEW_TURN_DECISION_TIMEOUT_SECONDS",
    )
    interview_turn_lease_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        validation_alias="APP_INTERVIEW_TURN_LEASE_SECONDS",
    )
    interview_turn_context_max_chars: int = Field(
        default=12_000,
        ge=2_000,
        le=50_000,
        validation_alias="APP_INTERVIEW_TURN_CONTEXT_MAX_CHARS",
    )
    interview_turn_recent_count: int = Field(
        default=6,
        ge=0,
        le=20,
        validation_alias="APP_INTERVIEW_TURN_RECENT_COUNT",
    )
    voice_turn_min_remaining_seconds: int = Field(
        default=30,
        ge=0,
        le=300,
        validation_alias="APP_VOICE_TURN_MIN_REMAINING_SECONDS",
    )
    voice_asr_url: str = Field(
        default="wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
        validation_alias="APP_VOICE_ASR_URL",
    )
    voice_asr_model: str = Field(
        default="qwen3-asr-flash-realtime",
        validation_alias="APP_VOICE_ASR_MODEL",
    )
    voice_asr_language: str = Field(
        default="zh",
        validation_alias="APP_VOICE_ASR_LANGUAGE",
    )
    voice_asr_format: str = Field(
        default="pcm",
        validation_alias="APP_VOICE_ASR_FORMAT",
    )
    voice_asr_sample_rate: int = Field(
        default=16000,
        validation_alias="APP_VOICE_ASR_SAMPLE_RATE",
    )
    voice_asr_enable_turn_detection: bool = Field(
        default=True,
        validation_alias="APP_VOICE_ASR_ENABLE_TURN_DETECTION",
    )
    voice_asr_turn_detection_type: str = Field(
        default="server_vad",
        validation_alias="APP_VOICE_ASR_TURN_DETECTION_TYPE",
    )
    voice_asr_turn_detection_threshold: float = Field(
        default=0,
        validation_alias="APP_VOICE_ASR_TURN_DETECTION_THRESHOLD",
    )
    voice_asr_silence_ms: int = Field(
        default=2000,
        validation_alias="APP_VOICE_ASR_SILENCE_MS",
    )
    voice_tts_model: str = Field(
        default="qwen3-tts-flash-realtime",
        validation_alias="APP_VOICE_TTS_MODEL",
    )
    voice_tts_url: str = Field(
        default="wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
        validation_alias="APP_VOICE_TTS_URL",
    )
    voice_tts_voice: str = Field(
        default="Cherry",
        validation_alias="APP_VOICE_TTS_VOICE",
    )
    voice_tts_format: str = Field(
        default="pcm",
        validation_alias="APP_VOICE_TTS_FORMAT",
    )
    voice_tts_sample_rate: int = Field(
        default=24000,
        validation_alias="APP_VOICE_TTS_SAMPLE_RATE",
    )
    voice_tts_mode: str = Field(
        default="commit",
        validation_alias="APP_VOICE_TTS_MODE",
    )
    voice_tts_language_type: str = Field(
        default="Chinese",
        validation_alias="APP_VOICE_TTS_LANGUAGE_TYPE",
    )
    voice_tts_speech_rate: float = Field(
        default=1,
        validation_alias="APP_VOICE_TTS_SPEECH_RATE",
    )
    voice_tts_volume: int = Field(
        default=60,
        validation_alias="APP_VOICE_TTS_VOLUME",
    )
    voice_tts_connect_timeout_seconds: float = Field(
        default=5,
        ge=1,
        validation_alias="APP_VOICE_TTS_CONNECT_TIMEOUT_SECONDS",
    )
    voice_tts_timeout_seconds: float = Field(
        default=8,
        ge=5,
        validation_alias="APP_VOICE_TTS_TIMEOUT_SECONDS",
    )
    voice_max_concurrent_tts_per_session: int = Field(
        default=3,
        ge=1,
        validation_alias="APP_VOICE_MAX_CONCURRENT_TTS_PER_SESSION",
    )
    voice_ai_question_max_chars: int = Field(
        default=120,
        ge=80,
        validation_alias="APP_VOICE_AI_QUESTION_MAX_CHARS",
    )
    voice_timeout_check_interval_seconds: float = Field(
        default=30,
        gt=0,
        validation_alias="APP_VOICE_TIMEOUT_CHECK_INTERVAL_SECONDS",
    )

    @model_validator(mode="after")
    def validate_competition_and_opentrek(self) -> Settings:
        if self.competition_mode and self.auth_registration_enabled:
            raise ValueError("比赛模式必须保持 APP_AUTH_REGISTRATION_ENABLED=false")
        try:
            mappings = json.loads(self.opentrek_kb_mappings_json)
        except ValueError as error:
            raise ValueError("APP_OPENTREK_KB_MAPPINGS_JSON 必须是合法 JSON") from error
        if not isinstance(mappings, (list, dict)):
            raise ValueError("APP_OPENTREK_KB_MAPPINGS_JSON 必须是数组或对象")
        if not self.opentrek_enabled:
            return self
        parsed = urlsplit(self.opentrek_runtime_base_url.strip())
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname != "10.128.203.200"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "APP_OPENTREK_RUNTIME_BASE_URL 只允许指向 10.128.203.200 的 HTTP(S) 地址"
            )
        required = {
            "APP_OPENTREK_APP_KEY": self.opentrek_app_key.get_secret_value(),
            "APP_OPENTREK_WORKSPACE_CODE": self.opentrek_workspace_code,
            "APP_OPENTREK_GENERAL_AGENT_CODE": self.opentrek_general_agent_code,
            "APP_OPENTREK_INTERVIEWER_AGENT_CODE": self.opentrek_interviewer_agent_code,
            "APP_OPENTREK_EVALUATOR_AGENT_CODE": self.opentrek_evaluator_agent_code,
            "APP_OPENTREK_RAG_AGENT_CODE": self.opentrek_rag_agent_code,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError(f"启用 OpenTrek 前必须配置: {', '.join(missing)}")
        return self

    otel_enabled: bool = Field(default=True, validation_alias="OTEL_ENABLED")
    otel_service_name: str = Field(
        default="interview-guide-api",
        validation_alias="OTEL_SERVICE_NAME",
    )
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None,
        validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )

    @property
    def allowed_origins(self) -> tuple[str, ...]:
        return tuple(
            origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()
        )

    @property
    def provider_outbound_allowed_host_list(self) -> tuple[str, ...]:
        return tuple(
            host.strip() for host in self.provider_outbound_allowed_hosts.split(",") if host.strip()
        )

    @property
    def provider_outbound_allowed_network_list(self) -> tuple[str, ...]:
        return tuple(
            network.strip()
            for network in self.provider_outbound_allowed_networks.split(",")
            if network.strip()
        )

    @property
    def opentrek_kb_mappings(self) -> dict[str, str]:
        raw = json.loads(self.opentrek_kb_mappings_json)
        if isinstance(raw, dict):
            items = list(raw.items())
        else:
            items = [
                (item.get("fileHash"), item.get("kbCode")) for item in raw if isinstance(item, dict)
            ]
        result: dict[str, str] = {}
        for file_hash, kb_code in items:
            normalized_hash = str(file_hash or "").strip().lower()
            normalized_code = str(kb_code or "").strip()
            if len(normalized_hash) != 64 or any(
                character not in "0123456789abcdef" for character in normalized_hash
            ):
                raise ValueError("OpenTrek 知识库映射包含无效的 SHA-256")
            if not normalized_code:
                raise ValueError("OpenTrek 知识库映射包含空 kbCode")
            if normalized_hash in result and result[normalized_hash] != normalized_code:
                raise ValueError("同一文件 SHA-256 不能映射到多个 OpenTrek 知识库")
            result[normalized_hash] = normalized_code
        return result

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
