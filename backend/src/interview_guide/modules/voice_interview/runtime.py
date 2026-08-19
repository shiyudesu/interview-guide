from __future__ import annotations

from datetime import datetime
from pathlib import Path

from interview_guide.common.ai.prompts import PromptRepository
from interview_guide.common.ai.skills import SkillRepository
from interview_guide.common.config.settings import Settings
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.modules.voice_interview.api import build_service
from interview_guide.modules.voice_interview.context import VoiceContextCompressor
from interview_guide.modules.voice_interview.dashscope import (
    DashScopeAsrProvider,
    DashScopeTtsSynthesizer,
)
from interview_guide.modules.voice_interview.llm import UnifiedVoiceLlmStreamer
from interview_guide.modules.voice_interview.protocols import (
    VoiceAsrProvider,
    VoiceLlmStreamer,
    VoiceTtsSynthesizer,
)
from interview_guide.modules.voice_interview.repository import (
    VoiceInterviewRepository,
)
from interview_guide.modules.voice_interview.websocket import (
    VoiceOpeningQuestions,
    VoiceWebSocketConfig,
    VoiceWebSocketRuntime,
)


def create_voice_websocket_runtime(
    infrastructure: RuntimeInfrastructure,
    settings: Settings,
) -> VoiceWebSocketRuntime:
    resources = Path(__file__).resolve().parents[4] / "resources"
    service = build_service(infrastructure)
    repository = VoiceInterviewRepository(
        infrastructure.database.sessions,
        datetime.now,
    )
    asr: VoiceAsrProvider = DashScopeAsrProvider(infrastructure.voice_config)
    tts: VoiceTtsSynthesizer = DashScopeTtsSynthesizer(
        infrastructure.voice_config,
        settings,
    )
    prompts = PromptRepository(resources)
    compressor = VoiceContextCompressor(
        infrastructure.provider_registry,
        infrastructure.llm_adapter,
        prompts,
        settings,
    )
    llm: VoiceLlmStreamer = UnifiedVoiceLlmStreamer(
        repository,
        infrastructure.provider_registry,
        infrastructure.llm_adapter,
        infrastructure.prompt_sanitizer,
        SkillRepository(resources),
        compressor,
    )
    return VoiceWebSocketRuntime(
        service,
        asr,
        llm,
        tts,
        VoiceOpeningQuestions.load(resources / "voice-interview-opening.yml"),
        config=VoiceWebSocketConfig(
            max_concurrent_tts=settings.voice_max_concurrent_tts_per_session,
            tts_sentence_timeout_seconds=settings.voice_tts_timeout_seconds,
            inactivity_check_seconds=settings.voice_timeout_check_interval_seconds,
            stream_push_interval_ms=settings.voice_llm_stream_push_interval_ms,
            stream_min_chars_delta=settings.voice_llm_stream_min_chars_delta,
            ai_question_max_chars=settings.voice_ai_question_max_chars,
        ),
    )
