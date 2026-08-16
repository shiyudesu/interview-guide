from __future__ import annotations

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
