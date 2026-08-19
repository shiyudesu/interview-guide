from __future__ import annotations

import base64
import time
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import (
    VoiceInterviewMessage,
    VoiceInterviewSession,
)
from interview_guide.main import create_app
from interview_guide.modules.voice_interview.fakes import (
    ExplicitFakeAsrProvider,
    ExplicitFakeLlmStreamer,
    ExplicitFakeTtsSynthesizer,
)
from interview_guide.modules.voice_interview.websocket import (
    VoiceOpeningQuestions,
    VoiceWebSocketConfig,
    VoiceWebSocketRuntime,
)


class InMemoryVoiceService:
    def __init__(self, sessions: list[VoiceInterviewSession]) -> None:
        self.sessions = {session.id: session for session in sessions}
        self.saved: list[tuple[int, str | None, str | None]] = []
        self.phases: list[str | None] = []
        self.end_calls: list[bool] = []
        self.pause_reasons: list[str] = []

    async def get_session(self, session_id: int | None) -> VoiceInterviewSession | None:
        return self.sessions.get(session_id) if session_id is not None else None

    async def history(self, session_id: int) -> list[VoiceInterviewMessage]:
        return [
            VoiceInterviewMessage(
                id=1,
                session_id=session_id,
                message_type="DIALOGUE",
                phase="TECH",
                user_recognized_text=None,
                ai_generated_text="已存在的问题",
                timestamp=datetime(2026, 8, 17, 8, 0),
                sequence_num=1,
                created_at=datetime(2026, 8, 17, 8, 0),
            )
        ]

    async def save_message(
        self,
        session_id: int,
        user_text: str | None,
        ai_text: str | None,
    ) -> None:
        self.saved.append((session_id, user_text, ai_text))

    async def start_phase(self, session_id: int, phase: str | None) -> None:
        self.sessions[session_id].current_phase = phase
        self.phases.append(phase)

    async def end_session(
        self,
        session_id: int,
        *,
        only_if_in_progress: bool = False,
    ) -> bool:
        self.end_calls.append(only_if_in_progress)
        session = self.sessions.get(session_id)
        if session is None:
            return False
        if only_if_in_progress and session.status != "IN_PROGRESS":
            return False
        session.status = "COMPLETED"
        return True

    async def pause_session(self, session_id: int, reason: str) -> None:
        self.sessions[session_id].status = "PAUSED"
        self.pause_reasons.append(reason)


def session(session_id: int, status: str = "IN_PROGRESS") -> VoiceInterviewSession:
    return VoiceInterviewSession(
        id=session_id,
        role_type="java-backend",
        skill_id="java-backend",
        status=status,
        current_phase="TECH",
        llm_provider="dashscope",
    )


def settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="voice-websocket-integration-key",
        APP_INFRASTRUCTURE_STARTUP_ENABLED=False,
        CORS_ALLOWED_ORIGINS="http://localhost:5173",
        OTEL_ENABLED=False,
    )


def build_runtime(
    service: InMemoryVoiceService,
    *,
    llm: ExplicitFakeLlmStreamer | None = None,
) -> tuple[
    VoiceWebSocketRuntime,
    ExplicitFakeAsrProvider,
    ExplicitFakeLlmStreamer,
    ExplicitFakeTtsSynthesizer,
]:
    asr = ExplicitFakeAsrProvider()
    effective_llm = llm or ExplicitFakeLlmStreamer(("一。二。三。四。",))
    tts = ExplicitFakeTtsSynthesizer(delay_seconds=0.01)
    runtime = VoiceWebSocketRuntime(
        service,
        asr,
        effective_llm,
        tts,
        VoiceOpeningQuestions(
            skill_questions={"java-backend": "固定开场。"},
            algorithm_skills=frozenset(),
            algorithm_question="算法开场。",
            backend_question="后端开场。",
        ),
        config=VoiceWebSocketConfig(
            inactivity_check_seconds=3600,
            asr_ready_check_seconds=3600,
        ),
    )
    return runtime, asr, effective_llm, tts


def test_real_fastapi_websocket_fake_voice_turn_protocol() -> None:
    active = session(1)
    service = InMemoryVoiceService([active])
    runtime, asr, llm, tts = build_runtime(service)
    app = create_app(settings())
    app.state.voice_websocket_runtime = runtime

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/ws/voice-interview/1",
            headers={"origin": "http://localhost:5173"},
        ) as websocket,
    ):
        assert websocket.receive_json()["action"] == "welcome"
        assert websocket.receive_json()["action"] == "asr_ready"
        websocket.send_json(
            {
                "type": "audio",
                "data": base64.b64encode(b"pcm").decode(),
            }
        )
        websocket.send_json(
            {
                "type": "control",
                "action": "submit",
                "data": {"text": "固定回答"},
            }
        )

        text_partial = websocket.receive_json()
        subtitle = websocket.receive_json()
        text_final = websocket.receive_json()
        chunks = [websocket.receive_json() for _ in range(4)]
        complete = websocket.receive_json()

        assert text_partial == {
            "type": "text",
            "content": "一。二。三。四。",
            "final": False,
        }
        assert subtitle == {
            "type": "subtitle",
            "text": "固定回答",
            "isFinal": True,
        }
        assert text_final["final"] is True
        assert [chunk["index"] for chunk in chunks] == [0, 1, 2, 3]
        assert all(chunk["isLast"] is False for chunk in chunks)
        assert all(base64.b64decode(chunk["data"]).startswith(b"RIFF") for chunk in chunks)
        assert complete["action"] == "audio_complete"

        websocket.send_json(
            {
                "type": "control",
                "action": "start_phase",
                "phase": "PROJECT",
            }
        )
        websocket.send_json({"type": "control", "action": "end_interview"})

    assert asr.sessions[0].appended_audio == [b"pcm"]
    assert llm.calls == [(1, "固定回答")]
    assert tts.max_active == 3
    assert service.saved == [(1, "固定回答", "一。二。三。四。")]
    assert service.phases == ["PROJECT"]
    assert service.end_calls == [False, True]
    assert active.status == "COMPLETED"


def test_websocket_validates_session_before_accepting() -> None:
    completed = session(2, "COMPLETED")
    service = InMemoryVoiceService([completed])
    runtime, _, _, _ = build_runtime(service)
    app = create_app(settings())
    app.state.voice_websocket_runtime = runtime

    with TestClient(app) as client:
        with (
            pytest.raises(WebSocketDisconnect) as missing,
            client.websocket_connect("/ws/voice-interview/999"),
        ):
            pass
        with (
            pytest.raises(WebSocketDisconnect) as finished,
            client.websocket_connect("/ws/voice-interview/2"),
        ):
            pass

    assert missing.value.code == 1008
    assert finished.value.code == 1008


def test_second_connection_overwrites_without_rejection_like_compatibility() -> None:
    active = session(3)
    service = InMemoryVoiceService([active])
    runtime, _, _, _ = build_runtime(service)
    app = create_app(settings())
    app.state.voice_websocket_runtime = runtime

    with (
        TestClient(app) as client,
        client.websocket_connect("/ws/voice-interview/3") as first,
    ):
        assert first.receive_json()["action"] == "welcome"
        assert first.receive_json()["action"] == "asr_ready"
        with client.websocket_connect("/ws/voice-interview/3") as second:
            error = second.receive_json()
            assert error["type"] == "error"
            assert "Session already exists: 3" in error["message"]


def test_oversized_text_message_is_rejected_at_handler_limit() -> None:
    active = session(5)
    service = InMemoryVoiceService([active])
    runtime, _, _, _ = build_runtime(service)
    app = create_app(settings())
    app.state.voice_websocket_runtime = runtime

    with TestClient(app) as client, client.websocket_connect("/ws/voice-interview/5") as websocket:
        assert websocket.receive_json()["action"] == "welcome"
        assert websocket.receive_json()["action"] == "asr_ready"
        websocket.send_text('{"type":"audio","data":"' + ("A" * (256 * 1024)) + '"}')
        error = websocket.receive_json()
        assert error == {
            "type": "error",
            "message": "消息处理失败: 消息大小超过限制",
        }


def test_disconnect_cancels_inflight_llm_and_auto_completes() -> None:
    active = session(4)
    service = InMemoryVoiceService([active])
    llm = ExplicitFakeLlmStreamer(("稍后回复。",), delay_seconds=5)
    runtime, _, effective_llm, _ = build_runtime(service, llm=llm)
    app = create_app(settings())
    app.state.voice_websocket_runtime = runtime

    with TestClient(app) as client, client.websocket_connect("/ws/voice-interview/4") as websocket:
        assert websocket.receive_json()["action"] == "welcome"
        assert websocket.receive_json()["action"] == "asr_ready"
        websocket.send_json(
            {
                "type": "control",
                "action": "submit",
                "data": {"text": "会中断的回答"},
            }
        )
        time.sleep(0.05)

    assert effective_llm.cancelled is True
    for _ in range(100):
        if active.status == "COMPLETED":
            break
        time.sleep(0.01)
    assert active.status == "COMPLETED"
