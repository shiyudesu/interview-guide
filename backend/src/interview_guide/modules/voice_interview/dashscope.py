from __future__ import annotations

import asyncio
import base64
import json
import logging
from types import TracebackType
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from websockets.asyncio.client import ClientConnection, connect

from interview_guide.common.config.settings import Settings
from interview_guide.modules.llm_provider.voice import (
    AsrConfig,
    TtsConfig,
)
from interview_guide.modules.voice_interview.protocols import (
    AsrAppendError,
    AsrErrorCallback,
    AsrNotReadyError,
    AsrReadyCallback,
    AsrTextCallback,
    VoiceAsrProvider,
    VoiceAsrSession,
)

logger = logging.getLogger(__name__)
ASR_READY_WAIT_SECONDS = 1.2
TTS_SDK_WAIT_SECONDS = 30


class VoiceConfigResolver(Protocol):
    async def asr_config(self, session_id: str) -> AsrConfig: ...

    async def tts_config(self, session_id: str) -> TtsConfig: ...


def _model_url(url: str, model: str) -> str:
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["model"] = model
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def extract_asr_text(message: dict[str, Any]) -> str | None:
    transcript = message.get("transcript")
    if isinstance(transcript, str):
        return transcript
    prefix = message.get("text")
    suffix = message.get("stash")
    if isinstance(prefix, str) or isinstance(suffix, str):
        combined = (prefix if isinstance(prefix, str) else "") + (
            suffix if isinstance(suffix, str) else ""
        )
        return combined or None
    delta = message.get("delta")
    if isinstance(delta, str):
        return delta
    if isinstance(delta, dict):
        for key in ("text", "transcript"):
            value = delta.get(key)
            if isinstance(value, str):
                return value
    item = message.get("item")
    if isinstance(item, dict):
        value = item.get("transcript")
        if isinstance(value, str):
            return value
    return None


class DashScopeAsrSession(VoiceAsrSession):
    def __init__(
        self,
        config: AsrConfig,
        *,
        on_ready: AsrReadyCallback,
        on_partial: AsrTextCallback,
        on_final: AsrTextCallback,
        on_error: AsrErrorCallback,
    ) -> None:
        self._config = config
        self._on_ready = on_ready
        self._on_partial = on_partial
        self._on_final = on_final
        self._on_error = on_error
        self._ready = asyncio.Event()
        self._send_lock = asyncio.Lock()
        self._connection: ClientConnection | None = None
        self._run_task: asyncio.Task[None] | None = None
        self._generation = 0
        self._closed = False

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    def start(self) -> None:
        self._generation += 1
        generation = self._generation
        self._run_task = asyncio.create_task(
            self._run(generation),
            name=f"voice-asr-{generation}",
        )

    async def append_audio(self, audio: bytes) -> None:
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=ASR_READY_WAIT_SECONDS)
        except TimeoutError as error:
            raise AsrNotReadyError("ASR session not ready") from error
        connection = self._connection
        if connection is None:
            raise AsrAppendError("No active session")
        try:
            async with self._send_lock:
                await connection.send(
                    json.dumps(
                        {
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(audio).decode(),
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
        except Exception as error:
            raise AsrAppendError("ASR append failed") from error

    async def restart(self) -> None:
        await self._stop_connection()
        await asyncio.sleep(0.2)
        if not self._closed:
            self.start()

    async def close(self) -> None:
        self._closed = True
        await self._stop_connection()

    async def _stop_connection(self) -> None:
        self._ready.clear()
        connection = self._connection
        self._connection = None
        if connection is not None:
            try:
                await connection.send('{"type":"session.finish"}')
            except Exception:
                logger.debug("failed to finish ASR session", exc_info=True)
            try:
                await connection.close()
            except Exception:
                logger.debug("failed to close ASR connection", exc_info=True)
        task = self._run_task
        self._run_task = None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _run(self, generation: int) -> None:
        try:
            async with connect(
                _model_url(self._config.url, self._config.model),
                additional_headers={
                    "Authorization": f"Bearer {self._config.api_key}",
                },
                open_timeout=10,
                max_size=2 * 1024 * 1024,
            ) as connection:
                if self._closed or generation != self._generation:
                    return
                self._connection = connection
                await connection.send(
                    json.dumps(
                        {
                            "type": "session.update",
                            "session": {
                                "modalities": ["text"],
                                "input_audio_format": self._config.format,
                                "sample_rate": self._config.sample_rate,
                                "input_audio_transcription": {
                                    "language": self._config.language,
                                },
                                "turn_detection": (
                                    {
                                        "type": self._config.turn_detection_type,
                                        "threshold": (self._config.turn_detection_threshold),
                                        "silence_duration_ms": (
                                            self._config.turn_detection_silence_duration_ms
                                        ),
                                    }
                                    if self._config.enable_turn_detection
                                    else None
                                ),
                            },
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
                self._ready.set()
                await self._on_ready()
                async for raw in connection:
                    if not isinstance(raw, str):
                        continue
                    await self._handle_message(json.loads(raw))
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not self._closed and generation == self._generation:
                await self._on_error(error)
        finally:
            if generation == self._generation:
                self._ready.clear()
                self._connection = None

    async def _handle_message(self, message: dict[str, Any]) -> None:
        event_type = message.get("type")
        if event_type == "conversation.item.input_audio_transcription.completed":
            text = extract_asr_text(message)
            if text:
                await self._on_final(text)
            return
        if event_type in {
            "conversation.item.input_audio_transcription.text",
            "conversation.item.input_audio_transcription.delta",
        }:
            text = extract_asr_text(message)
            if text:
                await self._on_partial(text)
            return
        if event_type == "error":
            error = message.get("error")
            detail = error.get("message") if isinstance(error, dict) else None
            await self._on_error(RuntimeError(str(detail or "Unknown ASR error")))


class DashScopeAsrProvider(VoiceAsrProvider):
    def __init__(self, config_store: VoiceConfigResolver) -> None:
        self._config_store = config_store

    async def open(
        self,
        session_id: str,
        *,
        on_ready: AsrReadyCallback,
        on_partial: AsrTextCallback,
        on_final: AsrTextCallback,
        on_error: AsrErrorCallback,
    ) -> DashScopeAsrSession:
        session = DashScopeAsrSession(
            await self._config_store.asr_config(session_id),
            on_ready=on_ready,
            on_partial=on_partial,
            on_final=on_final,
            on_error=on_error,
        )
        session.start()
        return session


class DashScopeTtsSynthesizer:
    def __init__(
        self,
        config_store: VoiceConfigResolver,
        settings: Settings,
    ) -> None:
        self._config_store = config_store
        self._connect_timeout = max(1, settings.voice_tts_connect_timeout_seconds)

    async def synthesize(self, session_id: str, text: str) -> bytes:
        if not text.strip():
            return b""
        config = await self._config_store.tts_config(session_id)
        try:
            return await self._synthesize(config, text)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("DashScope TTS synthesis failed", exc_info=True)
            return b""

    async def _synthesize(self, config: TtsConfig, text: str) -> bytes:
        audio = bytearray()
        async with asyncio.timeout(TTS_SDK_WAIT_SECONDS):
            async with connect(
                _model_url(config.url, config.model),
                additional_headers={"Authorization": f"Bearer {config.api_key}"},
                open_timeout=self._connect_timeout,
                max_size=2 * 1024 * 1024,
            ) as connection:
                await connection.send(
                    json.dumps(
                        {
                            "type": "session.update",
                            "session": {
                                "voice": config.voice,
                                "response_format": config.format,
                                "sample_rate": config.sample_rate,
                                "mode": config.mode,
                                "language_type": config.language_type,
                                "speech_rate": config.speech_rate,
                                "volume": config.volume,
                            },
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
                await connection.send(
                    json.dumps(
                        {"type": "input_text_buffer.append", "text": text},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
                await connection.send('{"type":"input_text_buffer.commit"}')
                async for raw in connection:
                    if not isinstance(raw, str):
                        continue
                    message = json.loads(raw)
                    event_type = message.get("type")
                    if event_type == "response.audio.delta":
                        encoded = message.get("delta", message.get("audio"))
                        if isinstance(encoded, str) and encoded:
                            audio.extend(base64.b64decode(encoded, validate=True))
                    elif event_type in {"response.done", "response.audio.done"}:
                        break
                    elif event_type == "error":
                        error = message.get("error")
                        detail = error.get("message") if isinstance(error, dict) else error
                        raise RuntimeError(str(detail or "Unknown TTS error"))
                try:
                    await connection.send('{"type":"session.finish"}')
                except Exception:
                    logger.debug("failed to finish TTS session", exc_info=True)
        return bytes(audio)

    async def __aenter__(self) -> DashScopeTtsSynthesizer:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
