from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.ai.encryption import ApiKeyEncryption
from interview_guide.common.ai.outbound import ProviderOutboundPolicy
from interview_guide.common.ai.providers import (
    ProviderRegistry,
    provider_now,
)
from interview_guide.common.ai.user_providers import (
    CURRENT_ENCRYPTION_VERSION,
    UserLlmProviderResolver,
    UserProviderRepository,
    normalize_provider_alias,
    provider_key_aad,
)
from interview_guide.common.db.models import UserLlmProviderConfig, VoiceInterviewSession
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.modules.llm_provider.models import (
    AsrConfigRequest,
    AsrConfigResponse,
    ProviderTestResult,
    TtsConfigRequest,
    TtsConfigResponse,
)
from interview_guide.modules.llm_provider.service import mask_api_key


@dataclass(frozen=True)
class AsrConfig:
    url: str
    model: str
    api_key: str
    language: str
    format: str
    sample_rate: int
    enable_turn_detection: bool
    turn_detection_type: str
    turn_detection_threshold: float
    turn_detection_silence_duration_ms: int


@dataclass(frozen=True)
class TtsConfig:
    url: str
    model: str
    api_key: str
    voice: str
    format: str
    sample_rate: int
    mode: str
    language_type: str
    speech_rate: float
    volume: int


class VoiceConfigService:
    def __init__(
        self,
        repository: UserProviderRepository,
        registry: ProviderRegistry,
        encryption: ApiKeyEncryption,
        outbound_policy: ProviderOutboundPolicy,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._encryption = encryption
        self._outbound_policy = outbound_policy

    async def asr(self) -> AsrConfigResponse:
        entity = await self._repository.voice_config()
        provider = await self._repository.get_provider_by_id(entity.asr_provider_id)
        api_key = self._decrypt_key(provider)
        return AsrConfigResponse(
            provider_id=provider.alias,
            url=entity.asr_url,
            model=entity.asr_model,
            masked_api_key=mask_api_key(api_key),
            language=entity.asr_language,
            format=entity.asr_format,
            sample_rate=entity.asr_sample_rate,
            enable_turn_detection=entity.asr_enable_turn_detection,
            turn_detection_type=entity.asr_turn_detection_type,
            turn_detection_threshold=entity.asr_turn_detection_threshold,
            turn_detection_silence_duration_ms=entity.asr_silence_ms,
        )

    async def asr_config(self) -> AsrConfig:
        entity = await self._repository.voice_config()
        await self._outbound_policy.validate_websocket_url(entity.asr_url)
        stored_provider = await self._repository.get_provider_by_id(entity.asr_provider_id)
        provider = await self._registry.get_voice(stored_provider.alias)
        return AsrConfig(
            url=entity.asr_url,
            model=entity.asr_model,
            api_key=provider.api_key,
            language=entity.asr_language,
            format=entity.asr_format,
            sample_rate=entity.asr_sample_rate,
            enable_turn_detection=entity.asr_enable_turn_detection,
            turn_detection_type=entity.asr_turn_detection_type,
            turn_detection_threshold=entity.asr_turn_detection_threshold,
            turn_detection_silence_duration_ms=entity.asr_silence_ms,
        )

    async def tts(self) -> TtsConfigResponse:
        entity = await self._repository.voice_config()
        provider = await self._repository.get_provider_by_id(entity.tts_provider_id)
        api_key = self._decrypt_key(provider)
        return TtsConfigResponse(
            provider_id=provider.alias,
            url=entity.tts_url,
            model=entity.tts_model,
            masked_api_key=mask_api_key(api_key),
            voice=entity.tts_voice,
            format=entity.tts_format,
            sample_rate=entity.tts_sample_rate,
            mode=entity.tts_mode,
            language_type=entity.tts_language_type,
            speech_rate=entity.tts_speech_rate,
            volume=entity.tts_volume,
        )

    async def tts_config(self) -> TtsConfig:
        entity = await self._repository.voice_config()
        await self._outbound_policy.validate_websocket_url(entity.tts_url)
        stored_provider = await self._repository.get_provider_by_id(entity.tts_provider_id)
        provider = await self._registry.get_voice(stored_provider.alias)
        return TtsConfig(
            url=entity.tts_url,
            model=entity.tts_model,
            api_key=provider.api_key,
            voice=entity.tts_voice,
            format=entity.tts_format,
            sample_rate=entity.tts_sample_rate,
            mode=entity.tts_mode,
            language_type=entity.tts_language_type,
            speech_rate=entity.tts_speech_rate,
            volume=entity.tts_volume,
        )

    async def update_asr(self, request: AsrConfigRequest) -> None:
        entity = await self._repository.voice_config()
        current_provider = await self._repository.get_provider_by_id(entity.asr_provider_id)
        provider_alias = normalize_provider_alias(request.provider_id) or current_provider.alias
        provider = await self._repository.get_provider(provider_alias)
        if request.url is not None:
            await self._outbound_policy.validate_websocket_url(request.url)
            if normalized_url(request.url) != normalized_url(entity.asr_url):
                self._require_key_for_url_change(request.api_key)
        await self._update_api_key(provider_alias, request.api_key)
        values: dict[str, object] = {
            "asr_provider_id": provider.id,
            "updated_at": provider_now(),
        }
        for name, value in (
            ("asr_url", request.url),
            ("asr_model", request.model),
            ("asr_language", request.language),
            ("asr_format", request.format),
            ("asr_sample_rate", request.sample_rate),
            ("asr_enable_turn_detection", request.enable_turn_detection),
            ("asr_turn_detection_type", request.turn_detection_type),
            ("asr_turn_detection_threshold", request.turn_detection_threshold),
            ("asr_silence_ms", request.turn_detection_silence_duration_ms),
        ):
            if value is not None:
                values[name] = value
        await self._repository.update_voice_config(values)

    async def update_tts(self, request: TtsConfigRequest) -> None:
        entity = await self._repository.voice_config()
        current_provider = await self._repository.get_provider_by_id(entity.tts_provider_id)
        provider_alias = normalize_provider_alias(request.provider_id) or current_provider.alias
        provider = await self._repository.get_provider(provider_alias)
        if request.url is not None:
            await self._outbound_policy.validate_websocket_url(request.url)
            if normalized_url(request.url) != normalized_url(entity.tts_url):
                self._require_key_for_url_change(request.api_key)
        await self._update_api_key(provider_alias, request.api_key)
        values: dict[str, object] = {
            "tts_provider_id": provider.id,
            "updated_at": provider_now(),
        }
        for name, value in (
            ("tts_url", request.url),
            ("tts_model", request.model),
            ("tts_voice", request.voice),
            ("tts_format", request.format),
            ("tts_sample_rate", request.sample_rate),
            ("tts_mode", request.mode),
            ("tts_language_type", request.language_type),
            ("tts_speech_rate", request.speech_rate),
            ("tts_volume", request.volume),
        ):
            if value is not None:
                values[name] = value
        await self._repository.update_voice_config(values)

    async def test_asr(self) -> ProviderTestResult:
        config = await self.asr_config()
        try:
            uri = urlsplit(config.url)
            if uri.hostname is None:
                raise ValueError("URI host is missing")
            port = uri.port or (443 if uri.scheme == "wss" else 80)
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(uri.hostname, port),
                timeout=5,
            )
            writer.close()
            await writer.wait_closed()
            return ProviderTestResult(
                success=True,
                message=f"ASR WebSocket 连接成功: {uri.hostname}",
                model=config.model,
            )
        except Exception as error:
            return ProviderTestResult(
                success=False,
                message=f"ASR 连接失败: {error}",
                model=config.model,
            )

    async def _update_api_key(self, provider_id: str, api_key: str | None) -> None:
        if api_key is None or not api_key.strip():
            return
        provider = await self._repository.get_provider(provider_id)
        encrypted = self._encryption.encrypt(
            api_key.strip(),
            aad=provider_key_aad(
                provider.user_id,
                provider.id,
                CURRENT_ENCRYPTION_VERSION,
            ),
        )
        await self._repository.update_provider(
            provider_id,
            {
                "api_key_nonce": encrypted.nonce,
                "api_key_ciphertext": encrypted.ciphertext,
                "encryption_version": CURRENT_ENCRYPTION_VERSION,
                "updated_at": provider_now(),
            },
        )
        await self._registry.publish_change()

    def _decrypt_key(self, provider: UserLlmProviderConfig) -> str:
        nonce = provider.api_key_nonce
        ciphertext = provider.api_key_ciphertext
        if nonce is None or ciphertext is None:
            return ""
        version = provider.encryption_version
        aad = (
            provider_key_aad(
                provider.user_id,
                provider.id,
                version,
            )
            if version >= CURRENT_ENCRYPTION_VERSION
            else None
        )
        return self._encryption.decrypt(nonce, ciphertext, aad=aad)

    @staticmethod
    def _require_key_for_url_change(api_key: str | None) -> None:
        if api_key is None or not api_key.strip():
            raise BusinessException(
                ErrorCode.BAD_REQUEST,
                "修改语音 WebSocket URL 时必须同时填写新的 API Key",
            )


def normalized_url(value: str) -> str:
    return value.strip().rstrip("/")


class UserVoiceConfigResolver:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        provider_resolver: UserLlmProviderResolver,
        encryption: ApiKeyEncryption,
        outbound_policy: ProviderOutboundPolicy,
    ) -> None:
        self._sessions = sessions
        self._provider_resolver = provider_resolver
        self._encryption = encryption
        self._outbound_policy = outbound_policy

    async def asr_config(self, session_id: str) -> AsrConfig:
        return await (await self._service(session_id)).asr_config()

    async def tts_config(self, session_id: str) -> TtsConfig:
        return await (await self._service(session_id)).tts_config()

    async def _service(self, session_id: str) -> VoiceConfigService:
        try:
            numeric_session_id = int(session_id)
        except ValueError as error:
            raise BusinessException(ErrorCode.VOICE_SESSION_NOT_FOUND) from error
        async with self._sessions() as session:
            user_id = await session.scalar(
                select(VoiceInterviewSession.user_id).where(
                    VoiceInterviewSession.id == numeric_session_id
                )
            )
        if not isinstance(user_id, UUID):
            raise BusinessException(ErrorCode.VOICE_SESSION_NOT_FOUND)
        resolver = self._provider_resolver
        scoped_registry = resolver.for_user(user_id)
        return VoiceConfigService(
            UserProviderRepository(self._sessions, user_id),
            scoped_registry,
            self._encryption,
            self._outbound_policy,
        )
