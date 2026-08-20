from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from interview_guide.common.ai.adapter import LlmAdapter, ProviderConfig
from interview_guide.common.ai.prompts import PromptRepository, PromptSanitizer
from interview_guide.common.ai.providers import (
    DASHSCOPE_BASE_URL,
    DASHSCOPE_CHAT_MODEL,
    DASHSCOPE_EMBEDDING_MODEL,
)
from interview_guide.common.ai.skills import SkillRepository
from interview_guide.common.ai.structured import StructuredOutputInvoker
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import InterviewQuestionRecord, InterviewSession
from interview_guide.modules.interview.models import QuestionKind
from interview_guide.modules.interview.question import InterviewSkillLibrary
from interview_guide.modules.interview.repository import SessionAggregate
from interview_guide.modules.interview.turn import InterviewTurnDecisionService
from interview_guide.modules.llm_provider.voice import AsrConfig, TtsConfig
from interview_guide.modules.voice_interview.dashscope import (
    DashScopeAsrProvider,
    DashScopeTtsSynthesizer,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPOSITORY_ROOT / ".artifacts/real-model-production.json"
TEXT = "这是生产模型验收。"


class AcceptanceVoiceConfig:
    def __init__(self, settings: Settings, api_key: str) -> None:
        self._asr = AsrConfig(
            url=settings.voice_asr_url,
            model=settings.voice_asr_model,
            api_key=api_key,
            language=settings.voice_asr_language,
            format=settings.voice_asr_format,
            sample_rate=settings.voice_asr_sample_rate,
            enable_turn_detection=settings.voice_asr_enable_turn_detection,
            turn_detection_type=settings.voice_asr_turn_detection_type,
            turn_detection_threshold=settings.voice_asr_turn_detection_threshold,
            turn_detection_silence_duration_ms=settings.voice_asr_silence_ms,
        )
        self._tts = TtsConfig(
            url=settings.voice_tts_url,
            model=settings.voice_tts_model,
            api_key=api_key,
            voice=settings.voice_tts_voice,
            format=settings.voice_tts_format,
            sample_rate=settings.voice_tts_sample_rate,
            mode=settings.voice_tts_mode,
            language_type=settings.voice_tts_language_type,
            speech_rate=settings.voice_tts_speech_rate,
            volume=settings.voice_tts_volume,
        )

    async def asr_config(self) -> AsrConfig:
        return self._asr

    async def tts_config(self) -> TtsConfig:
        return self._tts


async def verify_turn_decisions(
    settings: Settings,
    adapter: LlmAdapter,
    api_key: str,
) -> dict[str, Any]:
    resources = REPOSITORY_ROOT / "backend/resources"
    service = InterviewTurnDecisionService(
        StructuredOutputInvoker(adapter, max_attempts=1),
        PromptRepository(resources),
        PromptSanitizer(),
        InterviewSkillLibrary(SkillRepository(resources), resources),
        settings,
    )
    provider = ProviderConfig(
        provider_id="dashscope",
        base_url=DASHSCOPE_BASE_URL,
        api_key=api_key,
        model=DASHSCOPE_CHAT_MODEL,
    )
    now = datetime.now().replace(tzinfo=None)
    current_id = uuid.uuid4()
    next_id = uuid.uuid4()
    session = InterviewSession(
        id=1,
        channel="TEXT",
        context_json=None,
        completed_at=None,
        created_at=now,
        current_question_id=current_id,
        difficulty="mid",
        evaluate_error=None,
        evaluate_status=None,
        improvements_json=None,
        interview_category=None,
        knowledge_base_id=None,
        llm_provider="dashscope",
        max_follow_ups_per_main=1,
        overall_feedback=None,
        overall_score=None,
        planned_main_question_count=2,
        reference_answers_json=None,
        request_id=None,
        resume_id=None,
        session_id="acceptance",
        skill_id="java-backend",
        status="IN_PROGRESS",
        strengths_json=None,
    )
    questions = [
        InterviewQuestionRecord(
            id=current_id,
            interview_session_id=1,
            kind=QuestionKind.MAIN.value,
            phase=None,
            main_order=0,
            follow_up_order=0,
            parent_question_id=None,
            question="如何治理Redis缓存穿透？",
            type="REDIS",
            category="Redis",
            topic_summary="缓存穿透",
            reference_answer=None,
            key_points_json=None,
            scoring_rubric=None,
            source_context=None,
            source_question_id=None,
            created_at=now,
        ),
        InterviewQuestionRecord(
            id=next_id,
            interview_session_id=1,
            kind=QuestionKind.MAIN.value,
            phase=None,
            main_order=1,
            follow_up_order=0,
            parent_question_id=None,
            question="解释数据库事务隔离级别。",
            type="DATABASE",
            category="数据库",
            topic_summary="事务隔离",
            reference_answer=None,
            key_points_json=None,
            scoring_rubric=None,
            source_context=None,
            source_question_id=None,
            created_at=now,
        ),
    ]
    aggregate = SessionAggregate(session, "", questions, [])
    incomplete = await service.decide(provider, aggregate, "用布隆过滤器。")
    complete = await service.decide(
        provider,
        aggregate,
        "我会先用布隆过滤器拦截不存在的key，并结合短TTL空值缓存降低重复穿透；"
        "同时监控误判率和热点空key，布隆过滤器更新失败时降级到限流与数据库保护。",
    )
    if incomplete.action != "FOLLOW_UP" or not incomplete.follow_up_question:
        raise AssertionError("Incomplete answer did not produce a follow-up")
    if "布隆过滤器" not in incomplete.follow_up_question:
        raise AssertionError("Follow-up did not reference the submitted answer")
    if complete.action != "NEXT_MAIN":
        raise AssertionError("Complete answer did not advance to the next main question")
    return {
        "calls": 2,
        "completeAction": complete.action,
        "incompleteAction": incomplete.action,
        "incompleteReferencesAnswer": "布隆过滤器" in incomplete.follow_up_question,
        "schemaVersion": "v1",
        "totalTokens": (incomplete.total_tokens or 0) + (complete.total_tokens or 0),
    }


async def verify_voice(settings: Settings, api_key: str) -> dict[str, Any]:
    store = AcceptanceVoiceConfig(settings, api_key)
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
        OTEL_ENABLED=False,
    )
    api_key = os.environ["REAL_MODEL_API_KEY"]
    headers = {"Authorization": f"Bearer {api_key}"}
    chat_url = f"{DASHSCOPE_BASE_URL}/chat/completions"
    embedding_url = f"{DASHSCOPE_BASE_URL}/embeddings"
    samples: list[float] = []
    usage = {"inputTokens": 0, "outputTokens": 0}
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        for _ in range(5):
            started = time.perf_counter()
            response = await client.post(
                chat_url,
                headers=headers,
                json={
                    "model": DASHSCOPE_CHAT_MODEL,
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
                "model": DASHSCOPE_EMBEDDING_MODEL,
                "input": ["生产模型向量验收"],
                "dimensions": settings.ai_embedding_dimensions,
            },
        )
        embedding.raise_for_status()
        dimensions = len(embedding.json()["data"][0]["embedding"])
    if dimensions != settings.ai_embedding_dimensions:
        raise AssertionError(f"Unexpected embedding dimensions: {dimensions}")
    async with httpx.AsyncClient(timeout=120, trust_env=False) as turn_client:
        adapter = LlmAdapter(turn_client)
        turns = await verify_turn_decisions(settings, adapter, api_key)
    voice = await verify_voice(settings, api_key)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(
            {
                "calledAt": datetime.now(UTC).isoformat(),
                "chat": {
                    "calls": len(samples),
                    "medianMs": round(statistics.median(samples), 3),
                    "model": DASHSCOPE_CHAT_MODEL,
                    "usage": usage,
                },
                "embedding": {
                    "dimensions": dimensions,
                    "model": DASHSCOPE_EMBEDDING_MODEL,
                },
                "fakeModel": False,
                "passed": True,
                "provider": "dashscope",
                "turnDecisions": turns,
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
