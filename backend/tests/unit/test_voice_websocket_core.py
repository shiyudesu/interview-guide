from __future__ import annotations

import asyncio
import base64
import json
import uuid
from datetime import datetime
from typing import Any, cast

import pytest
from starlette.websockets import WebSocket

from interview_guide.common.db.models import (
    VoiceInterviewMessage,
    VoiceInterviewSession,
)
from interview_guide.modules.interview.models import (
    InterviewChannel,
    InterviewProgressDTO,
    InterviewQuestionDTO,
    InterviewSessionDTO,
    InterviewSessionStatus,
    QuestionKind,
    SubmitTurnResponse,
    TurnAction,
)
from interview_guide.modules.voice_interview.dashscope import extract_asr_text
from interview_guide.modules.voice_interview.fakes import (
    ExplicitFakeAsrProvider,
    ExplicitFakeTtsSynthesizer,
)
from interview_guide.modules.voice_interview.protocols import VoiceAsrSession
from interview_guide.modules.voice_interview.websocket import (
    ConcurrentWebSocket,
    VoiceConnection,
    VoiceSessionState,
    VoiceWebSocketConfig,
    VoiceWebSocketRuntime,
    join_segments,
    optimize_for_voice,
    pcm_to_wav,
)


def voice_session(session_id: int = 1, status: str = "IN_PROGRESS") -> VoiceInterviewSession:
    return VoiceInterviewSession(
        id=session_id,
        role_type="java-backend",
        skill_id="java-backend",
        status=status,
        current_phase="TECH",
        llm_provider="dashscope",
    )


class FakeVoiceService:
    def __init__(self, session: VoiceInterviewSession) -> None:
        self.sessions = {session.id: session}
        self.saved: list[tuple[int, str | None, str | None, uuid.UUID | None]] = []
        self.phases: list[tuple[int, str | None]] = []
        self.pause_reasons: list[str] = []
        self.end_calls: list[bool] = []
        self.history_rows: list[VoiceInterviewMessage] = [
            VoiceInterviewMessage(
                id=1,
                session_id=session.id,
                message_type="DIALOGUE",
                phase="TECH",
                user_recognized_text=None,
                ai_generated_text="已有问题",
                timestamp=datetime(2026, 8, 17, 8, 0),
                sequence_num=1,
                created_at=datetime(2026, 8, 17, 8, 0),
            )
        ]

    async def get_session(self, session_id: int | None) -> VoiceInterviewSession | None:
        return self.sessions.get(session_id) if session_id is not None else None

    async def history(self, session_id: int) -> list[VoiceInterviewMessage]:
        del session_id
        return self.history_rows

    async def save_message(
        self,
        session_id: int,
        user_text: str | None,
        ai_text: str | None,
        interview_turn_id: uuid.UUID | None = None,
    ) -> None:
        self.saved.append((session_id, user_text, ai_text, interview_turn_id))

    async def core_session(self, session_id: int) -> InterviewSessionDTO:
        question = InterviewQuestionDTO(
            question_id=uuid.uuid4(),
            kind=QuestionKind.MAIN,
            parent_question_id=None,
            question="固定问题",
            type="GENERAL",
            category="综合",
        )
        return InterviewSessionDTO(
            session_id=f"core-{session_id}",
            channel=InterviewChannel.VOICE,
            status=InterviewSessionStatus.IN_PROGRESS,
            current_question=question,
            turns=[],
            progress=InterviewProgressDTO(
                completed_main_questions=0,
                planned_main_questions=2,
                follow_ups_used_for_current_main=0,
                max_follow_ups_per_main=1,
            ),
            knowledge_base_id=None,
            interview_category=None,
        )

    async def submit_turn(
        self,
        session_id: int,
        request_id: str,
        answer: str,
    ) -> SubmitTurnResponse:
        del session_id, request_id, answer
        return SubmitTurnResponse(
            turn_id=uuid.uuid4(),
            action=TurnAction.NEXT_MAIN,
            acknowledgement="好的。",
            next_question=InterviewQuestionDTO(
                question_id=uuid.uuid4(),
                kind=QuestionKind.MAIN,
                parent_question_id=None,
                question="下一题是什么？",
                type="GENERAL",
                category="综合",
            ),
            completed=False,
            progress=InterviewProgressDTO(
                completed_main_questions=1,
                planned_main_questions=2,
                follow_ups_used_for_current_main=0,
                max_follow_ups_per_main=1,
            ),
        )

    async def start_phase(self, session_id: int, phase: str | None) -> None:
        self.phases.append((session_id, phase))

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
        self.pause_reasons.append(reason)
        self.sessions[session_id].status = "PAUSED"


class ManualClock:
    def __init__(self, now_ms: int = 0) -> None:
        self.value = now_ms
        self.sleeps: list[float] = []

    def now_ms(self) -> int:
        return self.value

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    def advance(self, milliseconds: int) -> None:
        self.value += milliseconds


class RecordingWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed: tuple[int, str | None] | None = None
        self.release = asyncio.Event()
        self.block = False
        self.active_sends = 0
        self.max_active_sends = 0

    async def send_text(self, payload: str) -> None:
        self.active_sends += 1
        self.max_active_sends = max(self.max_active_sends, self.active_sends)
        try:
            if self.block:
                await self.release.wait()
            self.sent.append(payload)
        finally:
            self.active_sends -= 1

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.closed = (code, reason)


def runtime(
    service: FakeVoiceService,
    *,
    asr: ExplicitFakeAsrProvider | None = None,
    tts: ExplicitFakeTtsSynthesizer | None = None,
    clock: ManualClock | None = None,
    config: VoiceWebSocketConfig | None = None,
) -> VoiceWebSocketRuntime:
    return VoiceWebSocketRuntime(
        service,
        asr or ExplicitFakeAsrProvider(),
        tts or ExplicitFakeTtsSynthesizer(),
        clock=clock,
        config=config,
    )


@pytest.mark.asyncio
async def test_voice_turn_uses_shared_decision_and_emits_tts() -> None:
    service = FakeVoiceService(voice_session())
    voice_runtime = runtime(service)
    raw = RecordingWebSocket()
    socket = ConcurrentWebSocket(
        cast(WebSocket, raw),
        send_timeout_seconds=1,
        send_buffer_limit_bytes=64 * 1024,
    )
    state = VoiceSessionState(tts_semaphore=asyncio.Semaphore(2))
    await voice_runtime.connections.register(VoiceConnection(1, socket, state))

    await voice_runtime._process_turn(1, state, "固定回答", "request_1234")

    documents = [json.loads(item) for item in raw.sent]
    assert any(
        item.get("type") == "control" and item.get("action") == "turn_deciding"
        for item in documents
    )
    assert any(
        item.get("type") == "text" and item.get("content") == "好的。 下一题是什么？"
        for item in documents
    )
    assert any(item.get("type") == "audio_chunk" for item in documents)
    assert service.saved[0][1:3] == ("固定回答", "好的。 下一题是什么？")


@pytest.mark.asyncio
async def test_concurrent_websocket_serializes_sends_and_enforces_buffer() -> None:
    raw = RecordingWebSocket()
    raw.block = True
    socket = ConcurrentWebSocket(
        cast(WebSocket, raw),
        send_timeout_seconds=1,
        send_buffer_limit_bytes=10,
    )

    first = asyncio.create_task(socket.send_text("12345"))
    await asyncio.sleep(0)
    assert await socket.send_text("123456") is False
    raw.release.set()
    assert await first is True

    raw.block = False
    await asyncio.gather(socket.send_text("a"), socket.send_text("b"))
    assert raw.max_active_sends == 1


@pytest.mark.asyncio
async def test_concurrent_websocket_swallows_send_timeout() -> None:
    raw = RecordingWebSocket()
    raw.block = True
    socket = ConcurrentWebSocket(
        cast(WebSocket, raw),
        send_timeout_seconds=0.01,
        send_buffer_limit_bytes=100,
    )

    assert await socket.send_text("timeout") is False


@pytest.mark.asyncio
async def test_audio_append_restart_retry_and_ai_cooldown_drop() -> None:
    session = voice_session()
    service = FakeVoiceService(session)
    clock = ManualClock(1000)
    asr_provider = ExplicitFakeAsrProvider(append_failures=(True, False))
    voice = runtime(service, asr=asr_provider, clock=clock)
    raw = RecordingWebSocket()
    socket = ConcurrentWebSocket(
        cast(WebSocket, raw),
        send_timeout_seconds=1,
        send_buffer_limit_bytes=1024,
    )
    state = VoiceSessionState(
        last_activity_ms=clock.now_ms(),
        tts_semaphore=asyncio.Semaphore(3),
    )
    connection = VoiceConnection(session.id, socket, state)
    await voice.connections.register(connection)
    state.asr = await asr_provider.open(
        str(session.id),
        on_ready=lambda: _no_result(),
        on_partial=lambda text: _ignore_text(text),
        on_final=lambda text: _ignore_text(text),
        on_error=lambda error: _ignore_error(error),
    )
    await cast(Any, state.asr).mark_ready()
    encoded = base64.b64encode(b"pcm").decode()

    await voice._handle_audio(session.id, encoded)

    fake_asr = asr_provider.sessions[0]
    assert fake_asr.restart_count == 1
    assert fake_asr.appended_audio == [b"pcm"]
    assert clock.sleeps == [0.08]

    state.ai_speaking = True
    await voice._handle_audio(session.id, encoded)
    state.ai_speaking = False
    state.ai_cooldown_until_ms = clock.now_ms() + 800
    await voice._handle_audio(session.id, encoded)
    assert fake_asr.appended_audio == [b"pcm"]
    clock.advance(800)
    await voice._handle_audio(session.id, encoded)
    assert fake_asr.appended_audio == [b"pcm", b"pcm"]


@pytest.mark.asyncio
async def test_injected_clock_warning_then_pause_cancels_session() -> None:
    session = voice_session()
    service = FakeVoiceService(session)
    clock = ManualClock()
    voice = runtime(service, clock=clock)
    raw = RecordingWebSocket()
    socket = ConcurrentWebSocket(
        cast(WebSocket, raw),
        send_timeout_seconds=1,
        send_buffer_limit_bytes=4096,
    )
    state = VoiceSessionState(
        last_activity_ms=0,
        tts_semaphore=asyncio.Semaphore(3),
    )
    await voice.connections.register(VoiceConnection(session.id, socket, state))

    clock.advance(270_001)
    assert await voice.check_inactivity(session.id) is False
    assert json.loads(raw.sent[-1])["action"] == "pause_timeout_warning"

    clock.advance(29_999)
    assert await voice.check_inactivity(session.id) is True
    assert service.pause_reasons == ["timeout"]
    assert session.status == "PAUSED"
    assert raw.closed == (1001, "Going away")
    await voice.disconnect(session.id)
    assert session.status == "PAUSED"
    assert service.end_calls == []


@pytest.mark.asyncio
async def test_partial_final_order_and_late_results_are_discarded() -> None:
    session = voice_session()
    service = FakeVoiceService(session)
    clock = ManualClock(1000)
    voice = runtime(service, clock=clock)
    raw = RecordingWebSocket()
    socket = ConcurrentWebSocket(
        cast(WebSocket, raw),
        send_timeout_seconds=1,
        send_buffer_limit_bytes=4096,
    )
    state = VoiceSessionState(
        last_activity_ms=clock.now_ms(),
        tts_semaphore=asyncio.Semaphore(3),
    )
    await voice.connections.register(VoiceConnection(session.id, socket, state))

    await voice._on_asr_text(session.id, "第一段", False)
    await voice._on_asr_text(session.id, "第一段", True)
    await voice._on_asr_text(session.id, "第二段", True)

    documents = [json.loads(value) for value in raw.sent]
    assert [value["text"] for value in documents] == [
        "第一段",
        "第一段",
        "第一段，第二段",
    ]
    assert all(value["isFinal"] is False for value in documents)

    state.processing = True
    await voice._on_asr_text(session.id, "迟到字幕", False)
    assert len(raw.sent) == 3


@pytest.mark.asyncio
async def test_asr_ready_monitor_restarts_twice_then_reports_timeout() -> None:
    session = voice_session()
    service = FakeVoiceService(session)
    clock = ManualClock()
    voice = runtime(service, clock=clock)
    raw = RecordingWebSocket()
    socket = ConcurrentWebSocket(
        cast(WebSocket, raw),
        send_timeout_seconds=1,
        send_buffer_limit_bytes=4096,
    )
    state = VoiceSessionState(
        last_activity_ms=0,
        tts_semaphore=asyncio.Semaphore(3),
    )
    asr = StuckAsrSession()
    state.asr = asr
    await voice.connections.register(VoiceConnection(session.id, socket, state))

    await voice._monitor_asr_ready(session.id, asr)

    documents = [json.loads(value) for value in raw.sent]
    assert asr.restart_count == 2
    assert [value.get("action") for value in documents[:-1]] == [
        "asr_reconnecting",
        "asr_reconnecting",
    ]
    assert documents[-1]["type"] == "error"
    assert clock.sleeps == [10, 10, 10]


class StuckAsrSession(VoiceAsrSession):
    def __init__(self) -> None:
        self.restart_count = 0

    @property
    def ready(self) -> bool:
        return False

    async def append_audio(self, audio: bytes) -> None:
        del audio

    async def restart(self) -> None:
        self.restart_count += 1

    async def close(self) -> None:
        return None


def test_protocol_helpers_use_expected_shapes() -> None:
    assert join_segments("第一段", "第二段") == "第一段，第二段"
    assert join_segments("第一段。", "第二段") == "第一段。 第二段"
    assert optimize_for_voice("", 120) == "请继续。"
    wav = pcm_to_wav(b"\x01\x02")
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    assert int.from_bytes(wav[24:28], "little") == 24_000
    assert wav[44:] == b"\x01\x02"
    assert extract_asr_text({"text": "北京", "stash": "天气"}) == "北京天气"


async def _no_result() -> None:
    return None


async def _ignore_text(text: str) -> None:
    del text


async def _ignore_error(error: Exception) -> None:
    del error
