from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.encryption import ApiKeyEncryption
from interview_guide.common.ai.providers import (
    DASHSCOPE_BASE_URL,
    DASHSCOPE_CHAT_MODEL,
    DASHSCOPE_EMBEDDING_DIMENSIONS,
    DASHSCOPE_EMBEDDING_MODEL,
    DASHSCOPE_PROVIDER_ID,
    PROVIDER_CHANGED_CHANNEL,
    PROVIDER_VERSION_KEY,
)
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import (
    UserAiSetting,
    UserLlmProviderConfig,
    UserVoiceSetting,
)
from interview_guide.common.errors import BusinessException, ErrorCode

CURRENT_ENCRYPTION_VERSION = 1


@dataclass(frozen=True)
class UserProviderDefaults:
    default_chat_provider_id: str
    default_embedding_provider_id: str


class UserProviderRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        user_id: UUID,
    ) -> None:
        self._sessions = sessions
        self.user_id = user_id

    async def ensure_defaults(self, settings: Settings, now: datetime) -> None:
        async with self._sessions() as session, session.begin():
            await ensure_user_provider_defaults(session, self.user_id, settings, now)

    async def provider_listing(
        self,
    ) -> tuple[UserProviderDefaults, list[UserLlmProviderConfig]]:
        async with self._sessions() as session:
            setting = await self._setting(session)
            providers = list(
                await session.scalars(
                    select(UserLlmProviderConfig)
                    .where(UserLlmProviderConfig.user_id == self.user_id)
                    .order_by(UserLlmProviderConfig.alias)
                )
            )
            aliases = {provider.id: provider.alias for provider in providers}
            return (
                UserProviderDefaults(
                    aliases[setting.default_chat_provider_id],
                    aliases[setting.default_embedding_provider_id],
                ),
                providers,
            )

    async def provider_detail(
        self,
        provider_id: str,
    ) -> tuple[UserProviderDefaults, UserLlmProviderConfig]:
        setting, providers = await self.provider_listing()
        provider = next((item for item in providers if item.alias == provider_id), None)
        if provider is None:
            raise BusinessException(
                ErrorCode.PROVIDER_NOT_FOUND,
                f"Provider '{provider_id}' 不存在",
            )
        return setting, provider

    async def get_provider(self, provider_id: str) -> UserLlmProviderConfig:
        async with self._sessions() as session:
            provider = await session.scalar(
                select(UserLlmProviderConfig).where(
                    UserLlmProviderConfig.user_id == self.user_id,
                    UserLlmProviderConfig.alias == provider_id,
                )
            )
            if provider is None:
                raise BusinessException(
                    ErrorCode.PROVIDER_NOT_FOUND,
                    f"Provider '{provider_id}' 不存在",
                )
            return provider

    async def get_provider_by_id(self, provider_id: UUID) -> UserLlmProviderConfig:
        async with self._sessions() as session:
            provider = await session.scalar(
                select(UserLlmProviderConfig).where(
                    UserLlmProviderConfig.user_id == self.user_id,
                    UserLlmProviderConfig.id == provider_id,
                )
            )
            if provider is None:
                raise BusinessException(ErrorCode.PROVIDER_NOT_FOUND)
            return provider

    async def default_aliases(self) -> UserProviderDefaults:
        defaults, _ = await self.provider_listing()
        return defaults

    async def voice_config(self) -> UserVoiceSetting:
        async with self._sessions() as session:
            config = await session.get(UserVoiceSetting, self.user_id)
            if config is None:
                raise BusinessException(
                    ErrorCode.VOICE_CONFIG_READ_FAILED,
                    "语音模型配置未初始化",
                )
            return config

    async def update_voice_config(self, values: dict[str, object]) -> None:
        async with self._sessions() as session, session.begin():
            config = await session.get(UserVoiceSetting, self.user_id, with_for_update=True)
            if config is None:
                raise BusinessException(ErrorCode.VOICE_CONFIG_READ_FAILED)
            for name, value in values.items():
                setattr(config, name, value)

    async def update_default_chat(self, provider_id: str, updated_at: datetime) -> None:
        async with self._sessions() as session, session.begin():
            provider = await self._provider_by_alias(session, provider_id)
            setting = await self._setting(session, for_update=True)
            setting.default_chat_provider_id = provider.id
            setting.updated_at = updated_at

    async def update_default_embedding(self, provider_id: str, updated_at: datetime) -> None:
        async with self._sessions() as session, session.begin():
            provider = await self._provider_by_alias(session, provider_id)
            if not provider.supports_embedding or not provider.embedding_model:
                raise BusinessException(
                    ErrorCode.BAD_REQUEST,
                    f"Provider '{provider_id}' 不支持 Embedding，不能设为默认向量服务",
                )
            setting = await self._setting(session, for_update=True)
            setting.default_embedding_provider_id = provider.id
            setting.updated_at = updated_at

    async def create_provider(self, provider: UserLlmProviderConfig) -> None:
        async with self._sessions() as session, session.begin():
            existing = await session.scalar(
                select(UserLlmProviderConfig.id).where(
                    UserLlmProviderConfig.user_id == self.user_id,
                    UserLlmProviderConfig.alias == provider.alias,
                )
            )
            if existing is not None:
                raise BusinessException(
                    ErrorCode.PROVIDER_ALREADY_EXISTS,
                    f"Provider '{provider.alias}' 已存在",
                )
            provider.user_id = self.user_id
            session.add(provider)

    async def update_provider(self, provider_id: str, values: dict[str, object]) -> None:
        async with self._sessions() as session, session.begin():
            provider = await self._provider_by_alias(session, provider_id, for_update=True)
            for name, value in values.items():
                setattr(provider, name, value)

    async def delete_provider(self, provider_id: str) -> None:
        async with self._sessions() as session, session.begin():
            provider = await self._provider_by_alias(session, provider_id, for_update=True)
            setting = await self._setting(session, for_update=True)
            voice = await session.get(UserVoiceSetting, self.user_id, with_for_update=True)
            referenced = {
                setting.default_chat_provider_id,
                setting.default_embedding_provider_id,
            }
            if voice is not None:
                referenced.update({voice.asr_provider_id, voice.tts_provider_id})
            if provider.id in referenced:
                raise BusinessException(
                    ErrorCode.PROVIDER_DEFAULT_CANNOT_DELETE,
                    f"Provider '{provider_id}' 正在使用中，请先切换默认配置",
                )
            await session.delete(provider)

    async def clear_for_tests(self) -> None:
        async with self._sessions() as session, session.begin():
            await session.execute(
                delete(UserVoiceSetting).where(UserVoiceSetting.user_id == self.user_id)
            )
            await session.execute(
                delete(UserAiSetting).where(UserAiSetting.user_id == self.user_id)
            )
            await session.execute(
                delete(UserLlmProviderConfig).where(UserLlmProviderConfig.user_id == self.user_id)
            )

    async def _provider_by_alias(
        self,
        session: AsyncSession,
        alias: str,
        *,
        for_update: bool = False,
    ) -> UserLlmProviderConfig:
        statement = select(UserLlmProviderConfig).where(
            UserLlmProviderConfig.user_id == self.user_id,
            UserLlmProviderConfig.alias == alias,
        )
        if for_update:
            statement = statement.with_for_update()
        provider = await session.scalar(statement)
        if provider is None:
            raise BusinessException(ErrorCode.PROVIDER_NOT_FOUND, f"Provider '{alias}' 不存在")
        return provider

    async def _setting(
        self,
        session: AsyncSession,
        *,
        for_update: bool = False,
    ) -> UserAiSetting:
        statement = select(UserAiSetting).where(UserAiSetting.user_id == self.user_id)
        if for_update:
            statement = statement.with_for_update()
        setting = await session.scalar(statement)
        if setting is None:
            raise BusinessException(
                ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                "默认 Provider 配置未初始化",
            )
        return setting


class ScopedProviderRegistry:
    def __init__(
        self,
        repository: UserProviderRepository,
        resolver: UserLlmProviderResolver,
    ) -> None:
        self._repository = repository
        self._resolver = resolver

    async def get_chat(self, provider_id: str | None = None) -> ProviderConfig:
        if provider_id is None:
            provider_id = (await self._repository.default_aliases()).default_chat_provider_id
        return await self._resolver.resolve(self._repository.user_id, provider_id)

    async def default_chat_alias(self) -> str:
        return (await self._repository.default_aliases()).default_chat_provider_id

    async def default_embedding_alias(self) -> str:
        return (await self._repository.default_aliases()).default_embedding_provider_id

    async def get_embedding(self, provider_id: str | None = None) -> ProviderConfig:
        if provider_id is None:
            provider_id = (await self._repository.default_aliases()).default_embedding_provider_id
        provider = await self._resolver.resolve(self._repository.user_id, provider_id)
        if not provider.supports_embedding or not provider.embedding_model:
            raise BusinessException(
                ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                f"Provider '{provider.provider_id}' 未配置可用的 Embedding 模型，"
                "无法执行知识库向量化",
            )
        return provider

    async def get_voice(self, provider_id: str) -> ProviderConfig:
        return await self._resolver.resolve(self._repository.user_id, provider_id)

    async def publish_change(self) -> int:
        return await self._resolver.publish_change(self._repository.user_id)

    async def reload(self) -> None:
        await self._resolver.publish_change(self._repository.user_id)


class UserLlmProviderResolver:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        encryption: ApiKeyEncryption,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._sessions = sessions
        self._encryption = encryption
        self._redis = redis
        self._settings = settings

    def for_user(self, user_id: UUID) -> ScopedProviderRegistry:
        repository = UserProviderRepository(self._sessions, user_id)
        return ScopedProviderRegistry(repository, self)

    async def resolve(self, user_id: UUID, alias: str) -> ProviderConfig:
        repository = UserProviderRepository(self._sessions, user_id)
        provider = await repository.get_provider(alias)
        api_key = self._decrypt_key(provider)
        if not api_key.strip():
            raise BusinessException(
                ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                f"Provider '{alias}' 未配置 API Key",
            )
        return ProviderConfig(
            provider_id=provider.alias,
            base_url=provider.base_url,
            api_key=api_key,
            model=provider.model,
            embedding_model=provider.embedding_model,
            embedding_dimensions=(
                provider.embedding_dimensions or self._settings.ai_embedding_dimensions
            ),
            supports_embedding=provider.supports_embedding,
            temperature=provider.temperature,
        )

    async def publish_change(self, user_id: UUID) -> int:
        version = int(await self._redis.incr(PROVIDER_VERSION_KEY))
        await self._redis.publish(
            PROVIDER_CHANGED_CHANNEL,
            f"{user_id}:{version}",
        )
        return version

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def _decrypt_key(self, provider: UserLlmProviderConfig) -> str:
        if provider.api_key_nonce is None or provider.api_key_ciphertext is None:
            return ""
        aad = (
            provider_key_aad(provider.user_id, provider.id, provider.encryption_version)
            if provider.encryption_version >= CURRENT_ENCRYPTION_VERSION
            else None
        )
        return self._encryption.decrypt(
            provider.api_key_nonce,
            provider.api_key_ciphertext,
            aad=aad,
        )


async def ensure_user_provider_defaults(
    session: AsyncSession,
    user_id: UUID,
    settings: Settings,
    now: datetime,
) -> UserLlmProviderConfig:
    existing = await session.scalar(
        select(UserLlmProviderConfig).where(
            UserLlmProviderConfig.user_id == user_id,
            UserLlmProviderConfig.alias == DASHSCOPE_PROVIDER_ID,
        )
    )
    provider = existing or UserLlmProviderConfig(
        id=uuid4(),
        user_id=user_id,
        alias=DASHSCOPE_PROVIDER_ID,
        api_key_ciphertext=None,
        api_key_nonce=None,
        encryption_version=CURRENT_ENCRYPTION_VERSION,
        base_url=DASHSCOPE_BASE_URL,
        builtin=True,
        created_at=now,
        embedding_dimensions=DASHSCOPE_EMBEDDING_DIMENSIONS,
        embedding_model=DASHSCOPE_EMBEDDING_MODEL,
        enabled=True,
        model=DASHSCOPE_CHAT_MODEL,
        supports_embedding=True,
        temperature=None,
        updated_at=now,
    )
    if existing is None:
        session.add(provider)
        await session.flush()
    if await session.get(UserAiSetting, user_id) is None:
        session.add(
            UserAiSetting(
                user_id=user_id,
                default_chat_provider_id=provider.id,
                default_embedding_provider_id=provider.id,
                created_at=now,
                updated_at=now,
            )
        )
    if await session.get(UserVoiceSetting, user_id) is None:
        session.add(
            UserVoiceSetting(
                user_id=user_id,
                asr_provider_id=provider.id,
                asr_url=settings.voice_asr_url,
                asr_model=settings.voice_asr_model,
                asr_language=settings.voice_asr_language,
                asr_format=settings.voice_asr_format,
                asr_sample_rate=settings.voice_asr_sample_rate,
                asr_enable_turn_detection=settings.voice_asr_enable_turn_detection,
                asr_turn_detection_type=settings.voice_asr_turn_detection_type,
                asr_turn_detection_threshold=settings.voice_asr_turn_detection_threshold,
                asr_silence_ms=settings.voice_asr_silence_ms,
                tts_provider_id=provider.id,
                tts_url=settings.voice_tts_url,
                tts_model=settings.voice_tts_model,
                tts_voice=settings.voice_tts_voice,
                tts_format=settings.voice_tts_format,
                tts_sample_rate=settings.voice_tts_sample_rate,
                tts_mode=settings.voice_tts_mode,
                tts_language_type=settings.voice_tts_language_type,
                tts_speech_rate=settings.voice_tts_speech_rate,
                tts_volume=settings.voice_tts_volume,
                updated_at=now,
            )
        )
    return provider


def provider_key_aad(user_id: UUID, provider_id: UUID, version: int) -> bytes:
    return f"provider-key:v{version}:{user_id}:{provider_id}".encode()
