from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from interview_guide.common.config.settings import Settings
from interview_guide.modules.llm_provider.voice import VoiceConfigStore
from interview_guide.modules.voice_interview.dashscope import (
    DashScopeAsrProvider,
    DashScopeTtsSynthesizer,
)

REPORT = Path("../migration/reports/real-model-production.json")
TEXT = "这是生产模型验收。"


async def verify_voice(settings: Settings) -> dict[str, Any]:
    store = VoiceConfigStore(settings)
    pcm = await DashScopeTtsSynthesizer(store, settings).synthesize(TEXT)
    if not pcm:
        raise AssertionError("TTS returned no PCM")
    ready = asyncio.Event()
    partial = asyncio.Event()

    async def mark_ready() -> None:
        ready.set()

    async def mark_partial(text: str) -> None:
        if text.strip():
            partial.set()

    async def on_error(error: Exception) -> None:
        raise error

    asr = await DashScopeAsrProvider(store).open(
        "production-acceptance",
        on_ready=mark_ready,
        on_partial=mark_partial,
        on_final=mark_partial,
        on_error=on_error,
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=15)
        await asr.append_audio(b"\x00\x00" * settings.voice_asr_sample_rate)
    finally:
        await asr.close()
    return {
        "asrModel": settings.voice_asr_model,
        "asrReady": ready.is_set(),
        "ttsModel": settings.voice_tts_model,
        "ttsOutputBytes": len(pcm),
    }


async def main() -> None:
    settings = Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="protected-production-model-check",
        AI_BAILIAN_API_KEY=os.environ["AI_BAILIAN_API_KEY"],
        OTEL_ENABLED=False,
    )
    headers = {"Authorization": f"Bearer {settings.ai_bailian_api_key.get_secret_value()}"}
    chat_url = f"{settings.ai_dashscope_base_url.rstrip('/')}/chat/completions"
    embedding_url = f"{settings.ai_dashscope_base_url.rstrip('/')}/embeddings"
    samples: list[float] = []
    usage = {"inputTokens": 0, "outputTokens": 0}
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        for _ in range(5):
            started = time.perf_counter()
            response = await client.post(
                chat_url,
                headers=headers,
                json={
                    "model": settings.ai_model,
                    "messages": [{"role": "user", "content": "Reply with OK only."}],
                    "max_tokens": 1,
                },
            )
            response.raise_for_status()
            payload = response.json()
            samples.append((time.perf_counter() - started) * 1000)
            raw_usage = payload.get("usage") or {}
            usage["inputTokens"] += int(raw_usage.get("prompt_tokens", 0) or 0)
            usage["outputTokens"] += int(raw_usage.get("completion_tokens", 0) or 0)
        embedding = await client.post(
            embedding_url,
            headers=headers,
            json={
                "model": settings.ai_embedding_model,
                "input": ["生产模型向量验收"],
                "dimensions": settings.ai_embedding_dimensions,
            },
        )
        embedding.raise_for_status()
        dimensions = len(embedding.json()["data"][0]["embedding"])
    if dimensions != settings.ai_embedding_dimensions:
        raise AssertionError(f"Unexpected embedding dimensions: {dimensions}")
    voice = await verify_voice(settings)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(
            {
                "calledAt": datetime.now(UTC).isoformat(),
                "chat": {
                    "calls": len(samples),
                    "medianMs": round(statistics.median(samples), 3),
                    "model": settings.ai_model,
                    "usage": usage,
                },
                "embedding": {
                    "dimensions": dimensions,
                    "model": settings.ai_embedding_model,
                },
                "fakeModel": False,
                "passed": True,
                "provider": "dashscope",
                "voice": voice,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(main())
