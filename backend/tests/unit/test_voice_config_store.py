from __future__ import annotations

from pathlib import Path

import pytest

from interview_guide.common.config.settings import Settings
from interview_guide.modules.llm_provider.models import (
    AsrConfigRequest,
    TtsConfigRequest,
)
from interview_guide.modules.llm_provider.voice import VoiceConfigStore


def settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="test-key",
        AI_BAILIAN_API_KEY="initial-voice-key",
        APP_VOICE_CONFIG_PATH=path,
    )


@pytest.mark.asyncio
async def test_asr_api_key_updates_tts_and_persists(tmp_path: Path) -> None:
    path = tmp_path / "voice.json"
    store = VoiceConfigStore(settings(path))

    await store.update_asr(
        AsrConfigRequest(
            model="asr-updated",
            api_key="shared-updated-key",
            sample_rate=8000,
        )
    )

    assert (await store.asr()).model == "asr-updated"
    assert (await store.asr()).sample_rate == 8000
    assert (await store.tts()).masked_api_key == "sha***key"
    reloaded = VoiceConfigStore(settings(path))
    await reloaded.start()
    assert (await reloaded.asr()).model == "asr-updated"
    assert (await reloaded.tts()).masked_api_key == "sha***key"


@pytest.mark.asyncio
async def test_tts_update_preserves_unset_fields(tmp_path: Path) -> None:
    store = VoiceConfigStore(settings(tmp_path / "voice.json"))
    before = await store.tts()

    await store.update_tts(TtsConfigRequest(voice="Updated"))
    after = await store.tts()

    assert after.voice == "Updated"
    assert after.model == before.model
    assert after.sample_rate == before.sample_rate
