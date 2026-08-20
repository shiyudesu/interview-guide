from __future__ import annotations

from typing import Literal

from pydantic import field_validator

from interview_guide.common.api.models import CamelModel


class ProviderResponse(CamelModel):
    id: str
    base_url: str
    masked_api_key: str
    has_api_key: bool
    model: str
    embedding_model: str | None
    embedding_dimensions: int
    supports_embedding: bool
    temperature: float | None
    default_chat_provider: bool
    default_embedding_provider: bool


class DefaultProviderRequest(CamelModel):
    default_provider: str | None = None
    default_embedding_provider: str | None = None


class CreateProviderRequest(CamelModel):
    id: str
    base_url: str
    api_key: str
    model: str
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    supports_embedding: bool | None = None
    temperature: float | None = None

    @field_validator("id", "base_url", "api_key", "model")
    @classmethod
    def required_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class UpdateProviderRequest(CamelModel):
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    supports_embedding: bool | None = None
    temperature: float | None = None


class AsrConfigResponse(CamelModel):
    provider_id: str
    enable_turn_detection: bool
    format: str
    language: str
    masked_api_key: str
    model: str
    sample_rate: int
    turn_detection_silence_duration_ms: int
    turn_detection_threshold: float
    turn_detection_type: str
    url: str


class AsrConfigRequest(CamelModel):
    provider_id: str | None = None
    url: str | None = None
    model: str | None = None
    api_key: str | None = None
    language: str | None = None
    format: str | None = None
    sample_rate: int | None = None
    enable_turn_detection: bool | None = None
    turn_detection_type: str | None = None
    turn_detection_threshold: float | None = None
    turn_detection_silence_duration_ms: int | None = None


class TtsConfigResponse(CamelModel):
    provider_id: str
    url: str
    format: str
    language_type: str
    masked_api_key: str
    mode: str
    model: str
    sample_rate: int
    speech_rate: float
    voice: str
    volume: int


class TtsConfigRequest(CamelModel):
    provider_id: str | None = None
    url: str | None = None
    model: str | None = None
    api_key: str | None = None
    voice: str | None = None
    format: str | None = None
    sample_rate: int | None = None
    mode: str | None = None
    language_type: str | None = None
    speech_rate: float | None = None
    volume: int | None = None


class ProviderTestResult(CamelModel):
    success: bool
    message: str
    model: str


class ModelDiscoveryRequest(CamelModel):
    provider_id: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    embedding_model: str | None = None
    refresh: bool = False


class ProviderModelList(CamelModel):
    chat_models: list[str]
    embedding_models: list[str]
    source: Literal["remote", "configured"]
    warning: str | None = None
