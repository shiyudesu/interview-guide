from __future__ import annotations

import builtins
import hashlib
import json
import logging
import re

import httpx
from redis.asyncio import Redis
from redis.exceptions import RedisError

from interview_guide.common.ai.encryption import ApiKeyEncryption
from interview_guide.common.ai.providers import (
    LlmProviderRegistry,
    ProviderRepository,
    provider_now,
)
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import LlmProviderConfig
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.modules.llm_provider.models import (
    CreateProviderRequest,
    DefaultProviderRequest,
    ModelDiscoveryRequest,
    ProviderModelList,
    ProviderResponse,
    ProviderTestResult,
    UpdateProviderRequest,
)

logger = logging.getLogger(__name__)
MODEL_LIST_CACHE_PREFIX = "llm:provider:models:"
MODEL_LIST_CACHE_TTL_SECONDS = 300
MODEL_LIST_LIMIT = 1000
NON_CHAT_MODEL_KIND = re.compile(
    r"(?:^|[-_/])(asr|tts|speech|audio|image|video|ocr|rerank|moderation)(?:[-_/]|$)"
)


def mask_api_key(api_key: str | None) -> str:
    if api_key is None or not api_key.strip():
        return "未配置"
    if len(api_key) <= 6:
        return "***"
    return f"{api_key[:3]}***{api_key[-3:]}"


def looks_like_chat_model(model: str) -> bool:
    normalized = model.lower()
    if "embedding" in normalized:
        return False
    return normalized.startswith(("glm-", "deepseek", "kimi", "moonshot", "qwen", "ernie"))


class LlmProviderService:
    def __init__(
        self,
        repository: ProviderRepository,
        registry: LlmProviderRegistry,
        encryption: ApiKeyEncryption,
        settings: Settings,
        redis: Redis,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._encryption = encryption
        self._settings = settings
        self._redis = redis

    async def list(self) -> list[ProviderResponse]:
        setting, providers = await self._repository.provider_listing()
        return [
            self._response(
                provider,
                setting.default_chat_provider_id,
                setting.default_embedding_provider_id,
            )
            for provider in providers
        ]

    async def get(self, provider_id: str) -> ProviderResponse:
        setting, provider = await self._repository.provider_detail(provider_id)
        return self._response(
            provider,
            setting.default_chat_provider_id,
            setting.default_embedding_provider_id,
        )

    async def defaults(self) -> DefaultProviderRequest:
        setting = await self._repository.global_setting()
        return DefaultProviderRequest(
            default_provider=setting.default_chat_provider_id,
            default_embedding_provider=setting.default_embedding_provider_id,
        )

    async def update_default_chat(
        self,
        request: DefaultProviderRequest,
    ) -> None:
        provider_id = self._required(
            request.default_provider,
            "defaultProvider 不能为空",
        )
        await self._repository.update_default_chat(
            provider_id,
            provider_now(),
        )
        await self._registry.publish_change()

    async def update_default_embedding(
        self,
        request: DefaultProviderRequest,
    ) -> None:
        provider_id = self._required(
            request.default_embedding_provider,
            "defaultEmbeddingProvider 不能为空",
        )
        await self._repository.update_default_embedding(
            provider_id,
            provider_now(),
        )
        await self._registry.publish_change()

    async def reload(self) -> None:
        await self._registry.reload()

    async def create(self, request: CreateProviderRequest) -> None:
        provider_id = self._required(request.id, "id 不能为空")
        base_url = self._required(request.base_url, "baseUrl 不能为空")
        model = self._required(request.model, "model 不能为空")
        api_key = self._required(request.api_key, "apiKey 不能为空")
        embedding_model = self._trim(request.embedding_model)
        dimensions = self._dimensions(request.embedding_dimensions)
        supports_embedding = (
            request.supports_embedding
            if request.supports_embedding is not None
            else embedding_model is not None
        )
        self._validate_embedding(
            provider_id,
            supports_embedding,
            embedding_model,
            dimensions,
        )
        encrypted = self._encryption.encrypt(api_key)
        timestamp = provider_now()
        await self._repository.create_provider(
            LlmProviderConfig(
                id=provider_id,
                api_key_ciphertext=encrypted.ciphertext,
                api_key_nonce=encrypted.nonce,
                base_url=base_url,
                builtin=False,
                created_at=timestamp,
                embedding_dimensions=dimensions,
                embedding_model=embedding_model,
                enabled=True,
                model=model,
                supports_embedding=supports_embedding,
                temperature=request.temperature,
                updated_at=timestamp,
            )
        )
        await self._registry.publish_change()

    async def update(
        self,
        provider_id: str,
        request: UpdateProviderRequest,
    ) -> None:
        provider = await self._repository.get_provider(provider_id)
        values: dict[str, object] = {}
        for field_name, value, message in (
            ("base_url", request.base_url, "baseUrl 不能为空字符串"),
            ("model", request.model, "model 不能为空字符串"),
            ("api_key", request.api_key, "apiKey 不能为空字符串"),
        ):
            trimmed = self._trim(value)
            if value is not None and trimmed is None:
                raise BusinessException(ErrorCode.BAD_REQUEST, message)
            if trimmed is not None and field_name != "api_key":
                values[field_name] = trimmed
        embedding_model = provider.embedding_model
        dimensions = provider.embedding_dimensions or self._settings.ai_embedding_dimensions
        supports_embedding = provider.supports_embedding
        if request.embedding_model is not None:
            embedding_model = self._trim(request.embedding_model)
            values["embedding_model"] = embedding_model
        if request.embedding_dimensions is not None:
            dimensions = self._dimensions(request.embedding_dimensions)
            values["embedding_dimensions"] = dimensions
        if request.supports_embedding is not None:
            supports_embedding = request.supports_embedding
            values["supports_embedding"] = supports_embedding
        self._validate_embedding(
            provider_id,
            supports_embedding,
            embedding_model,
            dimensions,
        )
        if request.temperature is not None:
            values["temperature"] = request.temperature
        trimmed_api_key = self._trim(request.api_key)
        if trimmed_api_key is not None:
            encrypted = self._encryption.encrypt(trimmed_api_key)
            values["api_key_nonce"] = encrypted.nonce
            values["api_key_ciphertext"] = encrypted.ciphertext
        values["updated_at"] = provider_now()
        await self._repository.update_provider(provider_id, values)
        await self._registry.publish_change()

    async def delete(self, provider_id: str) -> None:
        await self._repository.delete_provider(provider_id)
        await self._registry.publish_change()

    async def test(self, provider_id: str) -> ProviderTestResult:
        provider = await self._repository.get_provider(provider_id)
        api_key = self._encryption.decrypt(
            provider.api_key_nonce,
            provider.api_key_ciphertext,
        )
        if not api_key.strip():
            return ProviderTestResult(
                success=False,
                message="连接失败: Provider 未配置 API Key",
                model=provider.model,
            )
        candidates = connectivity_test_urls(provider.base_url)
        last_failure = "Unknown error"
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5, read=10, write=10, pool=5),
            follow_redirects=False,
        ) as client:
            for url in candidates:
                try:
                    response = await client.post(
                        url,
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={
                            "model": provider.model,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "Reply with OK only.",
                                }
                            ],
                            "max_tokens": 1,
                        },
                    )
                    response.raise_for_status()
                    return ProviderTestResult(
                        success=True,
                        message="连接成功",
                        model=provider.model,
                    )
                except httpx.HTTPStatusError as error:
                    body = abbreviate(error.response.text)
                    last_failure = f"HTTP {error.response.status_code} on {url}, body={body}"
                except Exception as error:
                    last_failure = f"{type(error).__name__} on {url}: {error}"
        return ProviderTestResult(
            success=False,
            message=f"连接失败: {last_failure}",
            model=provider.model,
        )

    async def discover_models(
        self,
        request: ModelDiscoveryRequest,
    ) -> ProviderModelList:
        provider = None
        provider_id = self._trim(request.provider_id)
        if provider_id is not None:
            provider = await self._repository.get_provider(provider_id)

        base_url = self._trim(request.base_url)
        if base_url is None and provider is not None:
            base_url = provider.base_url
        if base_url is None:
            raise BusinessException(ErrorCode.BAD_REQUEST, "baseUrl 不能为空")

        configured_chat = self._trim(request.model)
        configured_embedding = self._trim(request.embedding_model)
        if provider is not None:
            configured_chat = configured_chat or provider.model
            configured_embedding = configured_embedding or provider.embedding_model

        api_key = self._trim(request.api_key)
        if api_key is None and provider is not None:
            api_key = self._trim(
                self._encryption.decrypt(
                    provider.api_key_nonce,
                    provider.api_key_ciphertext,
                )
            )
        if api_key is None:
            if provider is not None:
                return ProviderModelList(
                    chat_models=optional_model_list(configured_chat),
                    embedding_models=optional_model_list(configured_embedding),
                    source="configured",
                    warning="Provider 未配置 API Key，无法拉取模型列表",
                )
            raise BusinessException(ErrorCode.BAD_REQUEST, "apiKey 不能为空")

        cache_key = model_list_cache_key(base_url, api_key)
        models = None if request.refresh else await self._read_cached_models(cache_key)
        warning = None
        if models is None:
            models, warning = await fetch_remote_models(base_url, api_key)
            if models:
                await self._write_cached_models(cache_key, models)

        if not models:
            return ProviderModelList(
                chat_models=optional_model_list(configured_chat),
                embedding_models=optional_model_list(configured_embedding),
                source="configured",
                warning=warning or "厂商未返回可用模型，当前仅显示已配置模型",
            )

        remote_chat, remote_embedding = classify_models(models)
        chat_models = configured_model_first(configured_chat, remote_chat)
        embedding_models = configured_model_first(
            configured_embedding,
            remote_embedding,
        )
        configured_missing: list[str] = []
        if configured_chat is not None and configured_chat not in models:
            configured_missing.append(configured_chat)
        if configured_embedding is not None and configured_embedding not in models:
            configured_missing.append(configured_embedding)
        if configured_missing:
            missing = "、".join(configured_missing)
            warning = f"当前配置模型未出现在厂商列表中，已保留供编辑：{missing}"
        return ProviderModelList(
            chat_models=chat_models,
            embedding_models=embedding_models,
            source="remote",
            warning=warning,
        )

    async def _read_cached_models(self, cache_key: str) -> builtins.list[str] | None:
        try:
            raw = await self._redis.get(cache_key)
        except RedisError:
            logger.warning("failed to read provider model cache", exc_info=True)
            return None
        if raw is None:
            return None
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return None
        return parse_model_ids(value)

    async def _write_cached_models(
        self,
        cache_key: str,
        models: builtins.list[str],
    ) -> None:
        try:
            await self._redis.setex(
                cache_key,
                MODEL_LIST_CACHE_TTL_SECONDS,
                json.dumps(models, ensure_ascii=False, separators=(",", ":")),
            )
        except RedisError:
            logger.warning("failed to write provider model cache", exc_info=True)

    def _response(
        self,
        provider: LlmProviderConfig,
        default_chat: str,
        default_embedding: str,
    ) -> ProviderResponse:
        api_key = self._encryption.decrypt(
            provider.api_key_nonce,
            provider.api_key_ciphertext,
        )
        return ProviderResponse(
            id=provider.id,
            base_url=provider.base_url,
            masked_api_key=mask_api_key(api_key),
            has_api_key=bool(api_key.strip()),
            model=provider.model,
            embedding_model=provider.embedding_model,
            embedding_dimensions=(
                provider.embedding_dimensions or self._settings.ai_embedding_dimensions
            ),
            supports_embedding=provider.supports_embedding,
            temperature=provider.temperature,
            default_chat_provider=provider.id == default_chat,
            default_embedding_provider=provider.id == default_embedding,
        )

    @staticmethod
    def _required(value: str | None, message: str) -> str:
        if value is None or not value.strip():
            raise BusinessException(ErrorCode.BAD_REQUEST, message)
        return value.strip()

    @staticmethod
    def _trim(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _dimensions(self, value: int | None) -> int:
        return value if value is not None and value > 0 else self._settings.ai_embedding_dimensions

    @staticmethod
    def _validate_embedding(
        provider_id: str,
        supports_embedding: bool,
        embedding_model: str | None,
        dimensions: int,
    ) -> None:
        if not supports_embedding:
            return
        if embedding_model is None:
            raise BusinessException(
                ErrorCode.BAD_REQUEST,
                "支持 Embedding 的 Provider 必须填写 embeddingModel",
            )
        if looks_like_chat_model(embedding_model):
            recommendations = {
                "dashscope": "text-embedding-v3",
                "glm": "embedding-3",
            }
            recommendation = recommendations.get(provider_id.lower())
            suffix = (
                f"，推荐填写 {recommendation}"
                if recommendation is not None
                else "，请填写该厂商真实的 Embedding 模型名"
            )
            raise BusinessException(
                ErrorCode.BAD_REQUEST,
                f"Embedding Model 不能填写聊天模型 '{embedding_model}'{suffix}",
            )
        if dimensions <= 0:
            raise BusinessException(ErrorCode.BAD_REQUEST, "向量维度必须为正整数")


def abbreviate(value: str | None) -> str:
    if value is None or not value.strip():
        return "[no body]"
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized if len(normalized) <= 200 else f"{normalized[:200]}..."


def connectivity_test_urls(base_url: str) -> list[str]:
    normalized = base_url.strip().rstrip("/")
    candidates = [f"{normalized}/chat/completions"]
    if not re.search(r"/v\d+[A-Za-z0-9]*$", normalized):
        candidates.append(f"{normalized}/v1/chat/completions")
    return list(dict.fromkeys(candidates))


def model_list_urls(base_url: str) -> list[str]:
    normalized = base_url.strip().rstrip("/")
    candidates = [f"{normalized}/models"]
    if not re.search(r"/v\d+[A-Za-z0-9]*$", normalized):
        candidates.append(f"{normalized}/v1/models")
    return list(dict.fromkeys(candidates))


def model_list_cache_key(base_url: str, api_key: str) -> str:
    identity = f"{base_url.strip().rstrip('/')}\0{api_key}".encode()
    return f"{MODEL_LIST_CACHE_PREFIX}{hashlib.sha256(identity).hexdigest()}"


async def fetch_remote_models(
    base_url: str,
    api_key: str,
) -> tuple[list[str], str | None]:
    last_failure = "Unknown error"
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5, read=10, write=10, pool=5),
        follow_redirects=False,
    ) as client:
        for url in model_list_urls(base_url):
            try:
                response = await client.get(
                    url,
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    },
                )
                response.raise_for_status()
                models = parse_model_ids(response.json())
                if not models:
                    last_failure = f"{url} 未返回模型 ID"
                    continue
                return models, None
            except httpx.HTTPStatusError as error:
                body = abbreviate(error.response.text)
                last_failure = f"HTTP {error.response.status_code} on {url}, body={body}"
            except (httpx.HTTPError, ValueError, TypeError) as error:
                last_failure = f"{type(error).__name__} on {url}: {error}"
    return [], f"模型列表拉取失败: {last_failure}"


def parse_model_ids(payload: object) -> list[str]:
    raw_models = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(raw_models, list):
        return []
    models: list[str] = []
    for item in raw_models:
        model_id = item.get("id") if isinstance(item, dict) else item
        if isinstance(model_id, str) and model_id.strip():
            models.append(model_id.strip())
        if len(models) >= MODEL_LIST_LIMIT:
            break
    return sorted(set(models), key=str.casefold)


def is_embedding_model(model: str) -> bool:
    normalized = model.casefold()
    return any(
        marker in normalized for marker in ("embedding", "embed", "text2vec", "bge-", "gte-")
    )


def is_chat_model(model: str) -> bool:
    normalized = model.casefold()
    return (
        not is_embedding_model(model)
        and "realtime" not in normalized
        and "livetranslate" not in normalized
        and NON_CHAT_MODEL_KIND.search(normalized) is None
    )


def classify_models(models: list[str]) -> tuple[list[str], list[str]]:
    chat_models = [model for model in models if is_chat_model(model)]
    embedding_models = [model for model in models if is_embedding_model(model)]
    return chat_models, embedding_models


def optional_model_list(model: str | None) -> list[str]:
    return [] if model is None else [model]


def configured_model_first(configured: str | None, models: list[str]) -> list[str]:
    if configured is None:
        return models
    return [configured, *(model for model in models if model != configured)]
