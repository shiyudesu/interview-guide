from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import urlsplit

from interview_guide.common.ai.encryption import ApiKeyEncryption
from interview_guide.common.ai.providers import (
    LlmProviderRegistry,
    ProviderRepository,
    provider_now,
)
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
        repository: ProviderRepository,
        registry: LlmProviderRegistry,
        encryption: ApiKeyEncryption,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._encryption = encryption

    async def asr(self) -> AsrConfigResponse:
        entity = await self._repository.voice_config()
        provider = await self._repository.get_provider(entity.asr_provider_id)
        api_key = self._encryption.decrypt(
            provider.api_key_nonce,
            provider.api_key_ciphertext,
        )
        return AsrConfigResponse(
            provider_id=entity.asr_provider_id,
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
        provider = await self._registry.get_voice(entity.asr_provider_id)
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
        provider = await self._repository.get_provider(entity.tts_provider_id)
        api_key = self._encryption.decrypt(
            provider.api_key_nonce,
            provider.api_key_ciphertext,
        )
        return TtsConfigResponse(
            provider_id=entity.tts_provider_id,
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
        provider = await self._registry.get_voice(entity.tts_provider_id)
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
        provider_id = request.provider_id or entity.asr_provider_id
        await self._repository.get_provider(provider_id)
        await self._update_api_key(provider_id, request.api_key)
        values: dict[str, object] = {
            "asr_provider_id": provider_id,
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
        provider_id = request.provider_id or entity.tts_provider_id
        await self._repository.get_provider(provider_id)
        await self._update_api_key(provider_id, request.api_key)
        values: dict[str, object] = {
            "tts_provider_id": provider_id,
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
        encrypted = self._encryption.encrypt(api_key.strip())
        await self._repository.update_provider(
            provider_id,
            {
                "api_key_nonce": encrypted.nonce,
                "api_key_ciphertext": encrypted.ciphertext,
                "updated_at": provider_now(),
            },
        )
        await self._registry.publish_change()
