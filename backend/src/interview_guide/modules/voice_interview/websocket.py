from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml
from starlette.websockets import WebSocket, WebSocketDisconnect

from interview_guide.common.db.models import (
    VoiceInterviewMessage,
    VoiceInterviewSession,
)
from interview_guide.modules.voice_interview.protocols import (
    AsrAppendError,
    AsrNotReadyError,
    VoiceAsrProvider,
    VoiceAsrSession,
    VoiceClock,
    VoiceLlmStreamer,
    VoiceTtsSynthesizer,
)

logger = logging.getLogger(__name__)
TERMINAL_PUNCTUATION = "。！？；!?;."
MARKDOWN_LIST = re.compile(r"(?m)^\s*[-*+]\s*")
WHITESPACE = re.compile(r"\s+")


class VoiceInterviewServicePort(Protocol):
    async def get_session(self, session_id: int | None) -> VoiceInterviewSession | None: ...

    async def history(self, session_id: int) -> list[VoiceInterviewMessage]: ...

    async def save_message(
        self,
        session_id: int,
        user_text: str | None,
        ai_text: str | None,
    ) -> None: ...

    async def start_phase(self, session_id: int, phase: str | None) -> None: ...

    async def end_session(
        self,
        session_id: int,
        *,
        only_if_in_progress: bool = False,
    ) -> bool: ...

    async def pause_session(self, session_id: int, reason: str) -> None: ...


class SystemVoiceClock(VoiceClock):
    def now_ms(self) -> int:
        return int(time.time() * 1000)

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


@dataclass(frozen=True)
class VoiceWebSocketConfig:
    input_message_limit_bytes: int = 256 * 1024
    send_timeout_seconds: float = 10
    send_buffer_limit_bytes: int = 512 * 1024
    asr_ready_check_seconds: float = 10
    asr_ready_restart_limit: int = 2
    asr_append_retry_count: int = 15
    asr_append_retry_seconds: float = 0.08
    submit_retry_seconds: float = 0.4
    max_concurrent_tts: int = 3
    tts_sentence_timeout_seconds: float = 8
    ai_cooldown_ms: int = 800
    inactivity_warning_ms: int = 270_000
    inactivity_pause_ms: int = 300_000
    inactivity_check_seconds: float = 30
    stream_push_interval_ms: int = 180
    stream_min_chars_delta: int = 12
    ai_question_max_chars: int = 120


@dataclass(frozen=True)
class VoiceOpeningQuestions:
    skill_questions: Mapping[str, str]
    algorithm_skills: frozenset[str]
    algorithm_question: str
    backend_question: str

    @classmethod
    def load(cls, path: Path) -> VoiceOpeningQuestions:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        raw = document["app"]["voice-interview"]["opening"]
        return cls(
            skill_questions={
                str(key): str(value).strip()
                for key, value in dict(raw.get("skill-questions", {})).items()
            },
            algorithm_skills=frozenset(str(value) for value in raw.get("algorithm-skills", ())),
            algorithm_question=str(raw.get("algorithm-question", "")).strip(),
            backend_question=str(raw.get("backend-question", "")).strip(),
        )

    def question(self, session: VoiceInterviewSession) -> str:
        skill_id = session.skill_id or ""
        configured = self.skill_questions.get(skill_id)
        if configured:
            return configured
        if skill_id in self.algorithm_skills:
            return self.algorithm_question
        return self.backend_question


class ConcurrentWebSocket:
    def __init__(
        self,
        websocket: WebSocket,
        *,
        send_timeout_seconds: float,
        send_buffer_limit_bytes: int,
    ) -> None:
        self._websocket = websocket
        self._send_timeout_seconds = send_timeout_seconds
        self._send_buffer_limit_bytes = send_buffer_limit_bytes
        self._send_lock = asyncio.Lock()
        self._buffer_lock = asyncio.Lock()
        self._buffered_bytes = 0
        self._open = True

    @property
    def open(self) -> bool:
        return self._open

    async def send_json(self, document: Mapping[str, Any]) -> bool:
        payload = json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return await self.send_text(payload)

    async def send_text(self, payload: str) -> bool:
        if not self._open:
            return False
        size = len(payload.encode())
        async with self._buffer_lock:
            if self._buffered_bytes + size > self._send_buffer_limit_bytes:
                logger.error("voice WebSocket send buffer limit exceeded")
                return False
            self._buffered_bytes += size
        try:
            async with self._send_lock:
                await asyncio.wait_for(
                    self._websocket.send_text(payload),
                    timeout=self._send_timeout_seconds,
                )
            return True
        except Exception:
            logger.exception("voice WebSocket send failed")
            return False
        finally:
            async with self._buffer_lock:
                self._buffered_bytes -= size

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        if not self._open:
            return
        self._open = False
        try:
            await self._websocket.close(code=code, reason=reason)
        except Exception:
            logger.debug("voice WebSocket close failed", exc_info=True)


@dataclass
class VoiceSessionState:
    merge_buffer: str = ""
    merge_started_at_ms: int = 0
    processing: bool = False
    ai_speaking: bool = False
    ai_cooldown_until_ms: int = 0
    last_activity_ms: int = 0
    asr: VoiceAsrSession | None = None
    tasks: set[asyncio.Task[Any]] = field(default_factory=set)
    tts_semaphore: asyncio.Semaphore | None = None

    def append_final(self, text: str, now_ms: int) -> None:
        segment = text.strip()
        if not segment:
            return
        if not self.merge_buffer:
            self.merge_buffer = segment
            self.merge_started_at_ms = now_ms
        else:
            self.merge_buffer = join_segments(self.merge_buffer, segment)

    def preview_with_partial(self, partial: str) -> str:
        value = partial.strip()
        if not value:
            return self.merge_buffer
        if not self.merge_buffer:
            return value
        return join_segments(self.merge_buffer, value)

    def take_utterance(self) -> str:
        value = self.merge_buffer
        self.merge_buffer = ""
        self.merge_started_at_ms = 0
        return value

    def blocks_audio(self, now_ms: int) -> bool:
        return self.ai_speaking or now_ms < self.ai_cooldown_until_ms


@dataclass(frozen=True)
class VoiceConnection:
    session_id: int
    socket: ConcurrentWebSocket
    state: VoiceSessionState


class VoiceConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, VoiceConnection] = {}
        self._lock = asyncio.Lock()

    async def register(self, connection: VoiceConnection) -> VoiceConnection | None:
        async with self._lock:
            previous = self._connections.get(connection.session_id)
            self._connections[connection.session_id] = connection
            return previous

    def current(self, session_id: int) -> VoiceConnection | None:
        return self._connections.get(session_id)

    async def pop(self, session_id: int) -> VoiceConnection | None:
        async with self._lock:
            return self._connections.pop(session_id, None)

    async def close_all(self) -> None:
        async with self._lock:
            connections = list(self._connections.values())
            self._connections.clear()
        for connection in connections:
            await connection.socket.close(code=1001, reason="Server shutdown")

    def session_ids(self) -> tuple[int, ...]:
        return tuple(self._connections)


class VoiceWebSocketRuntime:
    def __init__(
        self,
        service: VoiceInterviewServicePort,
        asr_provider: VoiceAsrProvider,
        llm: VoiceLlmStreamer,
        tts: VoiceTtsSynthesizer,
        opening: VoiceOpeningQuestions,
        *,
        clock: VoiceClock | None = None,
        config: VoiceWebSocketConfig | None = None,
    ) -> None:
        self._service = service
        self._asr_provider = asr_provider
        self._llm = llm
        self._tts = tts
        self._opening = opening
        self._clock = clock or SystemVoiceClock()
        self._config = config or VoiceWebSocketConfig()
        self.connections = VoiceConnectionManager()

    async def validate_session(self, session_id: int) -> VoiceInterviewSession | None:
        session = await self._service.get_session(session_id)
        if session is None or str(session.status) != "IN_PROGRESS":
            return None
        return session

    async def serve(
        self,
        websocket: WebSocket,
        session: VoiceInterviewSession,
    ) -> None:
        socket = ConcurrentWebSocket(
            websocket,
            send_timeout_seconds=self._config.send_timeout_seconds,
            send_buffer_limit_bytes=self._config.send_buffer_limit_bytes,
        )
        state = VoiceSessionState(
            last_activity_ms=self._clock.now_ms(),
            tts_semaphore=asyncio.Semaphore(self._config.max_concurrent_tts),
        )
        connection = VoiceConnection(session.id, socket, state)
        previous = await self.connections.register(connection)
        if previous is not None:
            state.asr = previous.state.asr
            state.tasks.update(previous.state.tasks)
            await self._send_error(
                socket,
                f"初始化语音识别失败: Session already exists: {session.id}",
            )
        else:
            try:
                state.asr = await self._open_asr(session.id)
                await socket.send_json(
                    {
                        "type": "control",
                        "action": "welcome",
                        "message": "连接成功，准备开始语音面试",
                        "timestamp": self._clock.now_ms(),
                    }
                )
                self._track(
                    state,
                    self._monitor_asr_ready(session.id, state.asr),
                    "voice-asr-ready",
                )
                self._track(
                    state,
                    self._monitor_inactivity(session.id),
                    "voice-inactivity",
                )
                self._track(
                    state,
                    self._send_opening_if_needed(session),
                    "voice-opening",
                )
            except Exception as error:
                await self._send_error(
                    socket,
                    f"初始化语音识别失败: {error}",
                )

        try:
            await self._receive_loop(websocket, session.id)
        finally:
            await self.disconnect(session.id)

    async def disconnect(self, session_id: int) -> None:
        connection = await self.connections.pop(session_id)
        if connection is not None:
            await self._cancel_tasks(connection.state)
            if connection.state.asr is not None:
                await connection.state.asr.close()
        try:
            await self._service.end_session(
                session_id,
                only_if_in_progress=True,
            )
        except Exception:
            logger.warning(
                "failed to auto-end voice session sessionId=%s",
                session_id,
                exc_info=True,
            )

    async def close(self) -> None:
        for session_id in self.connections.session_ids():
            current = self.connections.current(session_id)
            if current is not None:
                await current.socket.close(code=1001, reason="Server shutdown")
            await self.disconnect(session_id)
        await self.connections.close_all()

    async def _open_asr(self, session_id: int) -> VoiceAsrSession:
        return await self._asr_provider.open(
            str(session_id),
            on_ready=lambda: self._on_asr_ready(session_id),
            on_partial=lambda text: self._on_asr_text(session_id, text, False),
            on_final=lambda text: self._on_asr_text(session_id, text, True),
            on_error=lambda error: self._on_asr_error(session_id, error),
        )

    async def _receive_loop(self, websocket: WebSocket, session_id: int) -> None:
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return
                text = message.get("text")
                if not isinstance(text, str):
                    continue
                if len(text.encode()) > self._config.input_message_limit_bytes:
                    current = self.connections.current(session_id)
                    if current is not None:
                        await self._send_error(current.socket, "消息处理失败: 消息大小超过限制")
                        await current.socket.close(code=1009, reason="Message too big")
                    return
                await self._handle_text(session_id, text)
        except WebSocketDisconnect:
            return

    async def _handle_text(self, session_id: int, payload: str) -> None:
        current = self.connections.current(session_id)
        if current is None:
            return
        try:
            message = json.loads(payload)
            if not isinstance(message, dict):
                raise ValueError("消息必须是 JSON 对象")
            message_type = message.get("type")
            if not isinstance(message_type, str):
                raise ValueError("缺少消息类型")
            current.state.last_activity_ms = self._clock.now_ms()
            if message_type == "audio":
                data = message.get("data")
                if isinstance(data, str) and data:
                    await self._handle_audio(session_id, data)
                return
            if message_type == "control":
                await self._handle_control(session_id, message)
        except Exception as error:
            await self._send_error(current.socket, f"消息处理失败: {error}")

    async def _handle_audio(self, session_id: int, encoded: str) -> None:
        current = self.connections.current(session_id)
        if current is None or current.state.blocks_audio(self._clock.now_ms()):
            return
        try:
            audio = base64.b64decode(encoded, validate=True)
            asr = current.state.asr
            if asr is None:
                return
            await asr.append_audio(audio)
        except AsrNotReadyError:
            return
        except AsrAppendError:
            await self._restart_and_retry_audio(session_id, audio)
        except Exception as error:
            await self._send_error(current.socket, f"语音处理失败：{error}")

    async def _restart_and_retry_audio(self, session_id: int, audio: bytes) -> None:
        current = self.connections.current(session_id)
        if current is None or current.state.asr is None:
            return
        asr = current.state.asr
        await asr.restart()
        for _ in range(self._config.asr_append_retry_count):
            await self._clock.sleep(self._config.asr_append_retry_seconds)
            try:
                await asr.append_audio(audio)
                return
            except (AsrAppendError, AsrNotReadyError):
                continue
        current = self.connections.current(session_id)
        if current is not None:
            await self._send_error(
                current.socket,
                "语音识别连接中断，请刷新页面后重试",
            )

    async def _handle_control(
        self,
        session_id: int,
        message: Mapping[str, Any],
    ) -> None:
        action = message.get("action")
        if action == "submit":
            current = self.connections.current(session_id)
            if current is None:
                return
            data = message.get("data")
            if isinstance(data, dict):
                text = data.get("text")
                if isinstance(text, str) and text.strip():
                    current.state.merge_buffer = text.strip()
                    if current.state.merge_started_at_ms == 0:
                        current.state.merge_started_at_ms = self._clock.now_ms()
            await self._submit(session_id)
        elif action == "end_interview":
            await self._service.end_session(session_id)
        elif action == "start_phase":
            phase = message.get("phase")
            await self._service.start_phase(
                session_id,
                phase if isinstance(phase, str) else None,
            )

    async def _submit(self, session_id: int) -> None:
        current = self.connections.current(session_id)
        if current is None or not current.socket.open:
            return
        state = current.state
        if state.processing:
            self._track(
                state,
                self._delayed_submit(session_id),
                "voice-submit-retry",
            )
            return
        user_text = state.take_utterance().strip()
        if not user_text:
            return
        state.processing = True
        self._track(
            state,
            self._process_turn(session_id, state, user_text),
            "voice-turn",
        )

    async def _delayed_submit(self, session_id: int) -> None:
        await self._clock.sleep(self._config.submit_retry_seconds)
        await self._submit(session_id)

    async def _process_turn(
        self,
        session_id: int,
        state: VoiceSessionState,
        user_text: str,
    ) -> None:
        state.ai_speaking = True
        tts_tasks: list[tuple[int, asyncio.Task[bytes]]] = []
        try:
            session = await self._service.get_session(session_id)
            current = self.connections.current(session_id)
            if session is None or current is None or not current.socket.open:
                return
            raw = ""
            sentence_end = 0
            last_push_at = self._clock.now_ms()
            last_push_length = 0
            async for token in self._llm.stream(session, user_text):
                raw += token
                normalized = normalize_realtime_text(raw)
                sentence_end = self._start_complete_sentences(
                    state,
                    normalized,
                    sentence_end,
                    tts_tasks,
                )
                now = self._clock.now_ms()
                if (
                    now - last_push_at >= self._config.stream_push_interval_ms
                    and len(normalized) - last_push_length >= self._config.stream_min_chars_delta
                ):
                    current = self.connections.current(session_id)
                    if current is not None:
                        await self._send_text(current.socket, normalized, False)
                    last_push_at = now
                    last_push_length = len(normalized)

            normalized = normalize_realtime_text(raw)
            if len(normalized) > sentence_end:
                remaining = normalized[sentence_end:].strip()
                if remaining:
                    self._start_tts_task(
                        state,
                        len(tts_tasks),
                        remaining,
                        tts_tasks,
                    )
            ai_reply = optimize_for_voice(
                normalized,
                self._config.ai_question_max_chars,
            )
            current = self.connections.current(session_id)
            if current is None or not current.socket.open:
                return
            await self._send_text(current.socket, ai_reply, False)
            await self._send_subtitle(current.socket, user_text, True)
            await self._send_text(current.socket, ai_reply, True)
            await self._service.save_message(session_id, user_text, ai_reply)
            emitted = await self._emit_tts_chunks(session_id, tts_tasks)
            if emitted == 0 and tts_tasks:
                fallback = await self._synthesize_with_timeout(ai_reply, state)
                current = self.connections.current(session_id)
                if fallback and current is not None and current.socket.open:
                    await current.socket.send_json(
                        {
                            "type": "audio",
                            "data": base64.b64encode(pcm_to_wav(fallback)).decode(),
                            "text": ai_reply,
                        }
                    )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            current = self.connections.current(session_id)
            if current is not None:
                await self._send_error(current.socket, f"AI响应失败: {error}")
        finally:
            for _, task in tts_tasks:
                if not task.done():
                    task.cancel()
            if tts_tasks:
                await asyncio.gather(
                    *(task for _, task in tts_tasks),
                    return_exceptions=True,
                )
            state.ai_speaking = False
            state.ai_cooldown_until_ms = self._clock.now_ms() + self._config.ai_cooldown_ms
            state.processing = False

    def _start_complete_sentences(
        self,
        state: VoiceSessionState,
        normalized: str,
        sentence_end: int,
        tasks: list[tuple[int, asyncio.Task[bytes]]],
    ) -> int:
        while True:
            terminal = next(
                (
                    index
                    for index in range(sentence_end, len(normalized))
                    if normalized[index] in TERMINAL_PUNCTUATION
                ),
                None,
            )
            if terminal is None:
                return sentence_end
            sentence = normalized[sentence_end : terminal + 1].strip()
            sentence_end = terminal + 1
            if sentence:
                self._start_tts_task(state, len(tasks), sentence, tasks)

    def _start_tts_task(
        self,
        state: VoiceSessionState,
        index: int,
        sentence: str,
        tasks: list[tuple[int, asyncio.Task[bytes]]],
    ) -> None:
        task = asyncio.create_task(
            self._synthesize_with_timeout(sentence, state),
            name=f"voice-tts-{index}",
        )
        tasks.append((index, task))

    async def _synthesize_with_timeout(
        self,
        text: str,
        state: VoiceSessionState,
    ) -> bytes:
        semaphore = state.tts_semaphore
        assert semaphore is not None
        async with semaphore:
            try:
                return await asyncio.wait_for(
                    self._tts.synthesize(text),
                    timeout=self._config.tts_sentence_timeout_seconds,
                )
            except TimeoutError:
                return b""

    async def _emit_tts_chunks(
        self,
        session_id: int,
        tasks: list[tuple[int, asyncio.Task[bytes]]],
    ) -> int:
        emitted = 0
        for index, task in tasks:
            try:
                pcm = await task
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning(
                    "voice TTS sentence failed sessionId=%s index=%s",
                    session_id,
                    index,
                    exc_info=True,
                )
                continue
            current = self.connections.current(session_id)
            if not pcm or current is None or not current.socket.open:
                continue
            await current.socket.send_json(
                {
                    "type": "audio_chunk",
                    "data": base64.b64encode(pcm_to_wav(pcm)).decode(),
                    "index": index,
                    "isLast": False,
                }
            )
            emitted += 1
        current = self.connections.current(session_id)
        if emitted > 0 and current is not None:
            await current.socket.send_json(
                {
                    "type": "control",
                    "action": "audio_complete",
                    "message": "面试官语音播放完成",
                    "timestamp": self._clock.now_ms(),
                }
            )
        return emitted

    async def _on_asr_ready(self, session_id: int) -> None:
        current = self.connections.current(session_id)
        if current is not None:
            await current.socket.send_json(
                {
                    "type": "control",
                    "action": "asr_ready",
                    "message": "语音识别已就绪",
                    "timestamp": self._clock.now_ms(),
                }
            )

    async def _on_asr_error(self, session_id: int, error: Exception) -> None:
        current = self.connections.current(session_id)
        if current is not None:
            await self._send_error(
                current.socket,
                f"语音识别失败: {error}",
            )

    async def _on_asr_text(
        self,
        session_id: int,
        text: str,
        final: bool,
    ) -> None:
        current = self.connections.current(session_id)
        if current is None:
            return
        state = current.state
        if state.processing or state.blocks_audio(self._clock.now_ms()):
            return
        if final:
            state.append_final(text, self._clock.now_ms())
            await self._send_subtitle(current.socket, state.merge_buffer, False)
        else:
            await self._send_subtitle(
                current.socket,
                state.preview_with_partial(text),
                False,
            )

    async def _monitor_asr_ready(
        self,
        session_id: int,
        asr: VoiceAsrSession,
    ) -> None:
        await self._clock.sleep(self._config.asr_ready_check_seconds)
        for retry in range(self._config.asr_ready_restart_limit + 1):
            current = self.connections.current(session_id)
            if current is None or current.state.asr is not asr or asr.ready:
                return
            if retry >= self._config.asr_ready_restart_limit:
                await self._send_error(
                    current.socket,
                    "语音识别连接准备超时，请检查语音服务配置或稍后重试",
                )
                return
            await current.socket.send_json(
                {
                    "type": "control",
                    "action": "asr_reconnecting",
                    "message": "语音识别连接较慢，正在自动重连",
                    "timestamp": self._clock.now_ms(),
                }
            )
            await asr.restart()
            await self._clock.sleep(self._config.asr_ready_check_seconds)

    async def _monitor_inactivity(self, session_id: int) -> None:
        while True:
            await self._clock.sleep(self._config.inactivity_check_seconds)
            if await self.check_inactivity(session_id):
                return

    async def check_inactivity(self, session_id: int) -> bool:
        current = self.connections.current(session_id)
        if current is None:
            return True
        elapsed = self._clock.now_ms() - current.state.last_activity_ms
        if (
            elapsed > self._config.inactivity_warning_ms
            and elapsed < self._config.inactivity_pause_ms
        ):
            await current.socket.send_json(
                {
                    "type": "control",
                    "action": "pause_timeout_warning",
                    "message": "会话将在30秒后暂停，请继续说话或点击继续",
                    "timestamp": self._clock.now_ms(),
                }
            )
        elif elapsed >= self._config.inactivity_pause_ms:
            await self._pause_for_timeout(session_id)
            return True
        return False

    async def _pause_for_timeout(self, session_id: int) -> None:
        current = await self.connections.pop(session_id)
        if current is None:
            return
        await current.socket.send_json(
            {
                "type": "control",
                "action": "pause_timeout",
                "message": "会话因超时已暂停,可在历史记录中恢复",
                "timestamp": self._clock.now_ms(),
            }
        )
        await self._service.pause_session(session_id, "timeout")
        await self._cancel_tasks(
            current.state,
            exclude=asyncio.current_task(),
        )
        if current.state.asr is not None:
            await current.state.asr.close()
        await current.socket.close(code=1001, reason="Going away")

    async def _send_opening_if_needed(
        self,
        session: VoiceInterviewSession,
    ) -> None:
        history = await self._service.history(session.id)
        if history:
            return
        question = self._opening.question(session)
        if not question:
            return
        current = self.connections.current(session.id)
        if current is None or not current.socket.open:
            return
        await self._service.save_message(session.id, None, question)
        await self._send_text(current.socket, question, True)
        audio = await self._tts.synthesize(question)
        current = self.connections.current(session.id)
        if audio and current is not None and current.socket.open:
            await current.socket.send_json(
                {
                    "type": "audio",
                    "data": base64.b64encode(pcm_to_wav(audio)).decode(),
                    "text": question,
                }
            )

    @staticmethod
    async def _send_subtitle(
        socket: ConcurrentWebSocket,
        text: str,
        final: bool,
    ) -> None:
        await socket.send_json(
            {
                "type": "subtitle",
                "text": text,
                "isFinal": final,
            }
        )

    @staticmethod
    async def _send_text(
        socket: ConcurrentWebSocket,
        text: str,
        final: bool,
    ) -> None:
        await socket.send_json(
            {
                "type": "text",
                "content": text,
                "final": final,
            }
        )

    @staticmethod
    async def _send_error(socket: ConcurrentWebSocket, message: str) -> None:
        await socket.send_json({"type": "error", "message": message})

    @staticmethod
    def _track(
        state: VoiceSessionState,
        coroutine: Any,
        name: str,
    ) -> asyncio.Task[Any]:
        task = asyncio.create_task(coroutine, name=name)
        state.tasks.add(task)
        task.add_done_callback(state.tasks.discard)
        return task

    @staticmethod
    async def _cancel_tasks(
        state: VoiceSessionState,
        *,
        exclude: asyncio.Task[Any] | None = None,
    ) -> None:
        tasks = [task for task in tuple(state.tasks) if task is not exclude and not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        state.tasks.clear()


def join_segments(previous: str, next_value: str) -> str:
    left = previous.strip()
    right = next_value.strip()
    if right == left or right.startswith(left):
        return right
    if left.endswith(right):
        return left
    if left.endswith(tuple(TERMINAL_PUNCTUATION)):
        return f"{left} {right}"
    return f"{left}，{right}"


def normalize_realtime_text(content: str) -> str:
    if not content.strip():
        return ""
    return WHITESPACE.sub(
        " ",
        MARKDOWN_LIST.sub(
            "",
            content.replace("**", "").replace("```", "").replace("`", ""),
        ),
    ).strip()


def optimize_for_voice(content: str, max_chars: int) -> str:
    normalized = normalize_realtime_text(content)
    if not normalized:
        return "请继续。"
    effective_max = max(80, max_chars)
    if len(normalized) <= effective_max:
        return normalized
    truncated = normalized[:effective_max]
    terminal = max(truncated.rfind(value) for value in TERMINAL_PUNCTUATION)
    if terminal >= effective_max // 2:
        return truncated[: terminal + 1]
    return truncated + "…"


def pcm_to_wav(pcm: bytes) -> bytes:
    sample_rate = 24_000
    bits_per_sample = 16
    channels = 1
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = len(pcm)
    return b"".join(
        (
            b"RIFF",
            (data_size + 36).to_bytes(4, "little"),
            b"WAVEfmt ",
            (16).to_bytes(4, "little"),
            (1).to_bytes(2, "little"),
            channels.to_bytes(2, "little"),
            sample_rate.to_bytes(4, "little"),
            byte_rate.to_bytes(4, "little"),
            block_align.to_bytes(2, "little"),
            bits_per_sample.to_bytes(2, "little"),
            b"data",
            data_size.to_bytes(4, "little"),
            pcm,
        )
    )
