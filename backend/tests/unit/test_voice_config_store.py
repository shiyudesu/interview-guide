from __future__ import annotations

from types import SimpleNamespace

import pytest

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.encryption import ApiKeyEncryption
from interview_guide.modules.llm_provider.models import AsrConfigRequest, TtsConfigRequest
from interview_guide.modules.llm_provider.voice import VoiceConfigService


class FakeRepository:
    def __init__(self) -> None:
        encrypted = ApiKeyEncryption("test-key").encrypt("initial-voice-key")
        self.provider = SimpleNamespace(
            api_key_ciphertext=encrypted.ciphertext,
            api_key_nonce=encrypted.nonce,
        )
        self.entity = SimpleNamespace(
            asr_provider_id="dashscope",
            asr_url="wss://example.test/asr",
            asr_model="asr-initial",
            asr_language="zh",
            asr_format="pcm",
            asr_sample_rate=16000,
            asr_enable_turn_detection=True,
            asr_turn_detection_type="server_vad",
            asr_turn_detection_threshold=0.0,
            asr_silence_ms=2000,
            tts_provider_id="dashscope",
            tts_url="wss://example.test/tts",
            tts_model="tts-initial",
            tts_voice="Cherry",
            tts_format="pcm",
            tts_sample_rate=24000,
            tts_mode="commit",
            tts_language_type="Chinese",
            tts_speech_rate=1.0,
            tts_volume=60,
        )
        self.provider_updates: list[tuple[str, dict[str, object]]] = []

    async def voice_config(self):
        return self.entity

    async def get_provider(self, provider_id: str):
        del provider_id
        return self.provider

    async def update_voice_config(self, values: dict[str, object]) -> None:
        for name, value in values.items():
            setattr(self.entity, name, value)

    async def update_provider(self, provider_id: str, values: dict[str, object]) -> None:
        self.provider_updates.append((provider_id, values))


class FakeRegistry:
    def __init__(self) -> None:
        self.api_key = "initial-voice-key"
        self.publish_count = 0

    async def get_voice(self, provider_id: str) -> ProviderConfig:
        return ProviderConfig(
            provider_id=provider_id,
            base_url="https://example.test/v1",
            api_key=self.api_key,
            model="chat-model",
        )

    async def publish_change(self) -> int:
        self.publish_count += 1
        return self.publish_count


@pytest.mark.asyncio
async def test_asr_update_uses_database_config_and_provider_key() -> None:
    repository = FakeRepository()
    registry = FakeRegistry()
    service = VoiceConfigService(
        repository,  # type: ignore[arg-type]
        registry,  # type: ignore[arg-type]
        ApiKeyEncryption("test-key"),
    )

    await service.update_asr(
        AsrConfigRequest(
            provider_id="dashscope",
            model="asr-updated",
            api_key="shared-updated-key",
            sample_rate=8000,
        )
    )

    assert (await service.asr()).model == "asr-updated"
    assert (await service.asr()).sample_rate == 8000
    assert repository.provider_updates[0][0] == "dashscope"
    assert registry.publish_count == 1


@pytest.mark.asyncio
async def test_tts_update_preserves_unset_fields() -> None:
    repository = FakeRepository()
    service = VoiceConfigService(
        repository,  # type: ignore[arg-type]
        FakeRegistry(),  # type: ignore[arg-type]
        ApiKeyEncryption("test-key"),
    )
    before = await service.tts()

    await service.update_tts(TtsConfigRequest(voice="Updated"))
    after = await service.tts()

    assert after.voice == "Updated"
    assert after.model == before.model
    assert after.sample_rate == before.sample_rate
