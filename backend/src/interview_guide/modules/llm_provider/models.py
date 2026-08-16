from __future__ import annotations

from pydantic import field_validator

from interview_guide.common.api.models import CamelModel


class ProviderResponse(CamelModel):
    id: str
    base_url: str
    masked_api_key: str
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
