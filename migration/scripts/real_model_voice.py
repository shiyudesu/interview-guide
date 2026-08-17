#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import time
from array import array
from datetime import UTC, datetime
from pathlib import Path

from interview_guide.common.config.settings import Settings
from interview_guide.modules.llm_provider.voice import VoiceConfigStore
from interview_guide.modules.voice_interview.dashscope import (
    DashScopeAsrProvider,
    DashScopeTtsSynthesizer,
)

REPORT = Path("../migration/reports/real-model-voice.json")
FIXED_TEXT = "这是语音迁移真实模型连通性测试。"


def resample_pcm_24k_to_16k(pcm: bytes) -> bytes:
    source = array("h")
    source.frombytes(pcm)
    if not source:
        return b""
    target_count = len(source) * 2 // 3
    target = array(
        "h",
        (source[min(len(source) - 1, index * 3 // 2)] for index in range(target_count)),
    )
    return target.tobytes()


async def run() -> dict[str, object]:
    api_key = os.environ["AI_BAILIAN_API_KEY"]
    settings = Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="protected-real-model-voice",
        AI_BAILIAN_API_KEY=api_key,
        APP_VOICE_CONFIG_PATH="../migration/reports/real-voice-config.json",
        APP_VOICE_INTERVIEW_QWEN_ASR_URL=os.getenv(
            "APP_VOICE_INTERVIEW_QWEN_ASR_URL",
            "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
        ),
        APP_VOICE_INTERVIEW_QWEN_TTS_URL=os.getenv(
            "APP_VOICE_INTERVIEW_QWEN_TTS_URL",
            "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
        ),
        OTEL_ENABLED=False,
    )
    config = VoiceConfigStore(settings)
    tts = DashScopeTtsSynthesizer(config, settings)
    started = time.monotonic()
    pcm_24k = await tts.synthesize(FIXED_TEXT)
    if not pcm_24k:
        raise AssertionError("Real TTS returned empty PCM")
    pcm_16k = resample_pcm_24k_to_16k(pcm_24k)
    if not pcm_16k:
        raise AssertionError("TTS PCM resampling returned no audio")

    ready = asyncio.Event()
    final = asyncio.Event()
    transcripts: list[str] = []
    errors: list[str] = []

    async def on_ready() -> None:
        ready.set()

    async def on_text(text: str) -> None:
        transcripts.append(text)
        final.set()

    async def on_error(error: Exception) -> None:
        errors.append(type(error).__name__)

    asr = await DashScopeAsrProvider(config).open(
        "protected-real-model-voice",
        on_ready=on_ready,
        on_partial=lambda text: _ignore_text(text),
        on_final=on_text,
        on_error=on_error,
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=15)
        for offset in range(0, len(pcm_16k), 3200):
            await asr.append_audio(pcm_16k[offset : offset + 3200])
            await asyncio.sleep(0.1)
        await asyncio.wait_for(final.wait(), timeout=20)
    finally:
        await asr.close()

    if not transcripts[-1].strip():
        raise AssertionError("Real ASR returned an empty final transcript")
    return {
        "asr": {
            "audioFormat": settings.voice_asr_format,
            "inputSampleRate": settings.voice_asr_sample_rate,
            "model": settings.voice_asr_model,
            "transcriptLength": len(transcripts[-1]),
        },
        "calledAt": datetime.now(UTC).isoformat(),
        "elapsedMs": int((time.monotonic() - started) * 1000),
        "errors": errors,
        "provider": "dashscope",
        "realAsrTtsVerified": True,
        "tts": {
            "model": settings.voice_tts_model,
            "outputBytes": len(pcm_24k),
            "outputSampleRate": settings.voice_tts_sample_rate,
        },
    }


async def _ignore_text(text: str) -> None:
    del text


def main() -> None:
    report = asyncio.run(run())
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
