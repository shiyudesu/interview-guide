from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.encryption import ApiKeyEncryption
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import (
    LlmGlobalSetting,
    LlmProviderConfig,
    VoiceModelConfig,
)
from interview_guide.common.errors import BusinessException, ErrorCode

logger = logging.getLogger(__name__)
GLOBAL_SETTING_ID = 1
PROVIDER_VERSION_KEY = "llm:provider:config:version"
PROVIDER_CHANGED_CHANNEL = "llm:provider:config:changed"
PROVIDER_BOOTSTRAP_LOCK = 0x49475F50524F5644
VOICE_CONFIG_ID = 1
DASHSCOPE_PROVIDER_ID = "dashscope"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_CHAT_MODEL = "qwen3.7-max"
DASHSCOPE_EMBEDDING_MODEL = "qwen3.7-text-embedding"
DASHSCOPE_EMBEDDING_DIMENSIONS = 1024


@dataclass(frozen=True)
class ProviderSeed:
    provider_id: str
    base_url: str
    model: str
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    supports_embedding: bool = False
    temperature: float | None = None


def static_provider_seeds() -> tuple[ProviderSeed, ...]:
    return (
        ProviderSeed(
            DASHSCOPE_PROVIDER_ID,
            DASHSCOPE_BASE_URL,
            DASHSCOPE_CHAT_MODEL,
            DASHSCOPE_EMBEDDING_MODEL,
            DASHSCOPE_EMBEDDING_DIMENSIONS,
            True,
        ),
    )


class ProviderRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def bootstrap(
        self,
        settings: Settings,
        encryption: ApiKeyEncryption,
        now: Callable[[], datetime],
    ) -> None:
        async with self._sessions() as session, session.begin():
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": PROVIDER_BOOTSTRAP_LOCK},
            )
            count = await session.scalar(select(func.count()).select_from(LlmProviderConfig))
            if count == 0:
                timestamp = now()
                for seed in static_provider_seeds():
                    encrypted = encryption.encrypt("")
                    session.add(
                        LlmProviderConfig(
                            id=seed.provider_id,
                            api_key_ciphertext=encrypted.ciphertext,
                            api_key_nonce=encrypted.nonce,
                            base_url=seed.base_url,
                            builtin=True,
                            created_at=timestamp,
                            embedding_dimensions=(
                                seed.embedding_dimensions or settings.ai_embedding_dimensions
                            ),
                            embedding_model=seed.embedding_model,
                            enabled=True,
                            model=seed.model,
                            supports_embedding=seed.supports_embedding,
                            temperature=seed.temperature,
                            updated_at=timestamp,
                        )
                    )
            existing_setting = await session.get(
                LlmGlobalSetting,
                GLOBAL_SETTING_ID,
            )
            if existing_setting is None:
                timestamp = now()
                chat_provider = await self._existing_provider_or_first(
                    session,
                    DASHSCOPE_PROVIDER_ID,
                )
                embedding_provider = await self._existing_embedding_provider(
                    session,
                    DASHSCOPE_PROVIDER_ID,
                    chat_provider,
                )
                session.add(
                    LlmGlobalSetting(
                        id=GLOBAL_SETTING_ID,
                        created_at=timestamp,
                        default_chat_provider_id=chat_provider,
                        default_embedding_provider_id=embedding_provider,
                        updated_at=timestamp,
                    )
                )
            voice_config = await session.get(VoiceModelConfig, VOICE_CONFIG_ID)
            if voice_config is None:
                provider_id = await self._existing_provider_or_first(
                    session,
                    DASHSCOPE_PROVIDER_ID,
                )
                session.add(
                    VoiceModelConfig(
                        id=VOICE_CONFIG_ID,
                        asr_provider_id=provider_id,
                        asr_url=settings.voice_asr_url,
                        asr_model=settings.voice_asr_model,
                        asr_language=settings.voice_asr_language,
                        asr_format=settings.voice_asr_format,
                        asr_sample_rate=settings.voice_asr_sample_rate,
                        asr_enable_turn_detection=(settings.voice_asr_enable_turn_detection),
                        asr_turn_detection_type=(settings.voice_asr_turn_detection_type),
                        asr_turn_detection_threshold=(settings.voice_asr_turn_detection_threshold),
                        asr_silence_ms=settings.voice_asr_silence_ms,
                        tts_provider_id=provider_id,
                        tts_url=settings.voice_tts_url,
                        tts_model=settings.voice_tts_model,
                        tts_voice=settings.voice_tts_voice,
                        tts_format=settings.voice_tts_format,
                        tts_sample_rate=settings.voice_tts_sample_rate,
                        tts_mode=settings.voice_tts_mode,
                        tts_language_type=settings.voice_tts_language_type,
                        tts_speech_rate=settings.voice_tts_speech_rate,
                        tts_volume=settings.voice_tts_volume,
                        updated_at=now(),
                    )
                )

    async def provider_listing(
        self,
    ) -> tuple[LlmGlobalSetting, list[LlmProviderConfig]]:
        async with self._sessions() as session:
            setting = await session.get(LlmGlobalSetting, GLOBAL_SETTING_ID)
            if setting is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                    "读取 Provider 配置失败",
                )
            providers = await session.scalars(select(LlmProviderConfig))
            return setting, list(providers)

    async def provider_detail(
        self,
        provider_id: str,
    ) -> tuple[LlmGlobalSetting, LlmProviderConfig]:
        async with self._sessions() as session:
            setting = await session.get(LlmGlobalSetting, GLOBAL_SETTING_ID)
            if setting is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                    "读取 Provider 配置失败",
                )
            provider = await session.get(LlmProviderConfig, provider_id)
            if provider is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_NOT_FOUND,
                    f"Provider '{provider_id}' 不存在",
                )
            return setting, provider

    async def enabled_provider_listing(
        self,
    ) -> tuple[list[LlmProviderConfig], LlmGlobalSetting]:
        async with self._sessions() as session:
            providers = await session.scalars(
                select(LlmProviderConfig)
                .where(LlmProviderConfig.enabled.is_(True))
                .order_by(LlmProviderConfig.id)
            )
            setting = await session.get(LlmGlobalSetting, GLOBAL_SETTING_ID)
            if setting is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                    "读取 Provider 配置失败",
                )
            return list(providers), setting

    async def get_provider(self, provider_id: str) -> LlmProviderConfig:
        async with self._sessions() as session:
            provider = await session.get(LlmProviderConfig, provider_id)
            if provider is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_NOT_FOUND,
                    f"Provider '{provider_id}' 不存在",
                )
            return provider

    async def global_setting(self) -> LlmGlobalSetting:
        async with self._sessions() as session:
            setting = await session.get(LlmGlobalSetting, GLOBAL_SETTING_ID)
            if setting is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                    "读取 Provider 配置失败",
                )
            return setting

    async def voice_config(self) -> VoiceModelConfig:
        async with self._sessions() as session:
            config = await session.get(VoiceModelConfig, VOICE_CONFIG_ID)
            if config is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                    "语音模型配置未初始化",
                )
            return config

    async def update_voice_config(self, values: dict[str, object]) -> None:
        async with self._sessions() as session, session.begin():
            config = await session.get(VoiceModelConfig, VOICE_CONFIG_ID)
            if config is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                    "语音模型配置未初始化",
                )
            for name, value in values.items():
                setattr(config, name, value)

    async def update_model(self, provider_id: str, model: str) -> None:
        async with self._sessions() as session, session.begin():
            updated_id = await session.scalar(
                update(LlmProviderConfig)
                .where(LlmProviderConfig.id == provider_id)
                .values(model=model)
                .returning(LlmProviderConfig.id)
            )
            if updated_id is None:
                raise BusinessException(ErrorCode.PROVIDER_NOT_FOUND)

    async def update_default_chat(
        self,
        provider_id: str,
        updated_at: datetime,
    ) -> None:
        async with self._sessions() as session, session.begin():
            if await session.get(LlmProviderConfig, provider_id) is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_NOT_FOUND,
                    f"Provider '{provider_id}' 不存在",
                )
            setting = await session.get(LlmGlobalSetting, GLOBAL_SETTING_ID)
            if setting is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                    "默认 Provider 配置未初始化",
                )
            setting.default_chat_provider_id = provider_id
            setting.updated_at = updated_at

    async def update_default_embedding(
        self,
        provider_id: str,
        updated_at: datetime,
    ) -> None:
        async with self._sessions() as session, session.begin():
            provider = await session.get(LlmProviderConfig, provider_id)
            if provider is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_NOT_FOUND,
                    f"Provider '{provider_id}' 不存在",
                )
            if not provider.supports_embedding or not provider.embedding_model:
                raise BusinessException(
                    ErrorCode.BAD_REQUEST,
                    f"Provider '{provider_id}' 不支持 Embedding，不能设为默认向量服务",
                )
            setting = await session.get(LlmGlobalSetting, GLOBAL_SETTING_ID)
            if setting is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                    "默认 Provider 配置未初始化",
                )
            setting.default_embedding_provider_id = provider_id
            setting.updated_at = updated_at

    async def create_provider(self, provider: LlmProviderConfig) -> None:
        async with self._sessions() as session, session.begin():
            if await session.get(LlmProviderConfig, provider.id) is not None:
                raise BusinessException(
                    ErrorCode.PROVIDER_ALREADY_EXISTS,
                    f"Provider '{provider.id}' 已存在",
                )
            session.add(provider)

    async def update_provider(
        self,
        provider_id: str,
        values: dict[str, object],
    ) -> None:
        async with self._sessions() as session, session.begin():
            provider = await session.get(LlmProviderConfig, provider_id)
            if provider is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_NOT_FOUND,
                    f"Provider '{provider_id}' 不存在",
                )
            for name, value in values.items():
                setattr(provider, name, value)

    async def delete_provider(self, provider_id: str) -> None:
        async with self._sessions() as session, session.begin():
            setting = await session.get(LlmGlobalSetting, GLOBAL_SETTING_ID)
            if setting is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                    "默认 Provider 配置未初始化",
                )
            if provider_id in {
                setting.default_chat_provider_id,
                setting.default_embedding_provider_id,
            }:
                raise BusinessException(
                    ErrorCode.PROVIDER_DEFAULT_CANNOT_DELETE,
                    f"默认 Provider '{provider_id}' 不可删除，请先切换默认 Provider",
                )
            voice_provider_ids = await session.execute(
                select(
                    VoiceModelConfig.asr_provider_id,
                    VoiceModelConfig.tts_provider_id,
                ).where(VoiceModelConfig.id == VOICE_CONFIG_ID)
            )
            voice_provider = voice_provider_ids.one_or_none()
            if voice_provider is not None and provider_id in {
                voice_provider.asr_provider_id,
                voice_provider.tts_provider_id,
            }:
                raise BusinessException(
                    ErrorCode.PROVIDER_DEFAULT_CANNOT_DELETE,
                    f"语音服务正在使用 Provider '{provider_id}'，请先切换语音 Provider",
                )
            provider = await session.get(LlmProviderConfig, provider_id)
            if provider is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_NOT_FOUND,
                    f"Provider '{provider_id}' 不存在",
                )
            await session.delete(provider)

    async def clear_for_tests(self) -> None:
        async with self._sessions() as session, session.begin():
            await session.execute(delete(VoiceModelConfig))
            await session.execute(delete(LlmGlobalSetting))
            await session.execute(delete(LlmProviderConfig))

    @staticmethod
    async def _existing_provider_or_first(
        session: AsyncSession,
        preferred: str,
    ) -> str:
        if await session.get(LlmProviderConfig, preferred) is not None:
            return preferred
        first = await session.scalar(
            select(LlmProviderConfig.id).order_by(LlmProviderConfig.id).limit(1)
        )
        return str(first or "dashscope")

    @staticmethod
    async def _existing_embedding_provider(
        session: AsyncSession,
        preferred: str,
        fallback: str,
    ) -> str:
        result = await session.scalar(
            select(LlmProviderConfig.id)
            .where(
                LlmProviderConfig.id == preferred,
                LlmProviderConfig.enabled.is_(True),
                LlmProviderConfig.supports_embedding.is_(True),
                LlmProviderConfig.embedding_model.is_not(None),
            )
            .limit(1)
        )
        if result is not None:
            return str(result)
        result = await session.scalar(
            select(LlmProviderConfig.id)
            .where(
                LlmProviderConfig.enabled.is_(True),
                LlmProviderConfig.supports_embedding.is_(True),
                LlmProviderConfig.embedding_model.is_not(None),
            )
            .order_by(LlmProviderConfig.id)
            .limit(1)
        )
        return str(result or fallback)


class LlmProviderRegistry:
    def __init__(
        self,
        repository: ProviderRepository,
        encryption: ApiKeyEncryption,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._encryption = encryption
        self._redis = redis
        self._settings = settings
        self._providers: dict[str, ProviderConfig] = {}
        self._default_chat = DASHSCOPE_PROVIDER_ID
        self._default_embedding = DASHSCOPE_PROVIDER_ID
        self._version = -1
        self._lock = asyncio.Lock()
        self._listener_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        await self.reload()
        self._version = await self._read_version()
        self._listener_task = asyncio.create_task(self._listen())

    async def close(self) -> None:
        if self._listener_task is None:
            return
        self._listener_task.cancel()
        await asyncio.gather(self._listener_task, return_exceptions=True)
        self._listener_task = None

    async def reload(self) -> None:
        async with self._lock:
            providers, setting = await self._repository.enabled_provider_listing()
            self._providers = {
                provider.id: ProviderConfig(
                    provider_id=provider.id,
                    base_url=provider.base_url,
                    api_key=self._encryption.decrypt(
                        provider.api_key_nonce,
                        provider.api_key_ciphertext,
                    ),
                    model=provider.model,
                    embedding_model=provider.embedding_model,
                    embedding_dimensions=(
                        provider.embedding_dimensions or self._settings.ai_embedding_dimensions
                    ),
                    supports_embedding=provider.supports_embedding,
                    temperature=provider.temperature,
                )
                for provider in providers
            }
            self._default_chat = setting.default_chat_provider_id
            self._default_embedding = setting.default_embedding_provider_id

    async def get_chat(self, provider_id: str | None = None) -> ProviderConfig:
        await self._refresh_if_stale()
        return self._get(provider_id or self._default_chat)

    async def get_embedding(
        self,
        provider_id: str | None = None,
    ) -> ProviderConfig:
        await self._refresh_if_stale()
        provider = self._get(provider_id or self._default_embedding)
        if not provider.supports_embedding or not provider.embedding_model:
            raise BusinessException(
                ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                f"Provider '{provider.provider_id}' 未配置可用的 Embedding 模型，"
                "无法执行知识库向量化",
            )
        return provider

    async def get_voice(self, provider_id: str) -> ProviderConfig:
        await self._refresh_if_stale()
        return self._get(provider_id)

    async def publish_change(self) -> int:
        version = int(await self._redis.incr(PROVIDER_VERSION_KEY))
        await self._redis.publish(PROVIDER_CHANGED_CHANNEL, str(version))
        self._version = version
        await self.reload()
        return version

    def _get(self, provider_id: str) -> ProviderConfig:
        try:
            provider = self._providers[provider_id]
        except KeyError as error:
            raise BusinessException(
                ErrorCode.PROVIDER_NOT_FOUND,
                f"Unknown LLM provider: {provider_id}",
            ) from error
        if not provider.api_key.strip():
            raise BusinessException(
                ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                f"Provider '{provider_id}' 未配置 API Key",
            )
        return provider

    async def _refresh_if_stale(self) -> None:
        version = await self._read_version()
        if version != self._version:
            await self.reload()
            self._version = version

    async def _read_version(self) -> int:
        value = await self._redis.get(PROVIDER_VERSION_KEY)
        return int(value) if value is not None else 0

    async def _listen(self) -> None:
        while True:
            try:
                async with self._redis.pubsub() as pubsub:
                    await pubsub.subscribe(PROVIDER_CHANGED_CHANNEL)
                    async for message in pubsub.listen():
                        if message.get("type") != "message":
                            continue
                        self._version = -1
                        await self.reload()
                        self._version = int(message["data"])
            except asyncio.CancelledError:
                raise
            except RedisError:
                logger.exception("provider invalidation listener failed")
                await asyncio.sleep(1)


def provider_now() -> datetime:
    return datetime.now()
