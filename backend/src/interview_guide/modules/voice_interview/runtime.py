from __future__ import annotations

from interview_guide.common.config.settings import Settings
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.metrics import ApplicationMetrics
from interview_guide.modules.voice_interview.api import build_service
from interview_guide.modules.voice_interview.dashscope import (
    DashScopeAsrProvider,
    DashScopeTtsSynthesizer,
)
from interview_guide.modules.voice_interview.protocols import (
    VoiceAsrProvider,
    VoiceTtsSynthesizer,
)
from interview_guide.modules.voice_interview.websocket import (
    VoiceWebSocketConfig,
    VoiceWebSocketRuntime,
)


def create_voice_websocket_runtime(
    infrastructure: RuntimeInfrastructure,
    settings: Settings,
    metrics: ApplicationMetrics | None = None,
) -> VoiceWebSocketRuntime:
    service = build_service(infrastructure, settings, metrics)
    asr: VoiceAsrProvider = DashScopeAsrProvider(infrastructure.voice_config_resolver)
    tts: VoiceTtsSynthesizer = DashScopeTtsSynthesizer(
        infrastructure.voice_config_resolver,
        settings,
    )
    return VoiceWebSocketRuntime(
        service,
        asr,
        tts,
        config=VoiceWebSocketConfig(
            max_concurrent_tts=settings.voice_max_concurrent_tts_per_session,
            tts_sentence_timeout_seconds=settings.voice_tts_timeout_seconds,
            inactivity_check_seconds=settings.voice_timeout_check_interval_seconds,
            ai_question_max_chars=settings.voice_ai_question_max_chars,
        ),
    )
