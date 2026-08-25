from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import pytest
from websockets.asyncio.server import ServerConnection, serve

from interview_guide.common.config.settings import Settings
from interview_guide.modules.llm_provider.voice import AsrConfig, TtsConfig
from interview_guide.modules.voice_interview.dashscope import (
    DashScopeAsrProvider,
    DashScopeTtsSynthesizer,
)


def settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="voice-protocol-test-key",
        OTEL_ENABLED=False,
    )


class StaticVoiceConfig:
    def __init__(self, asr_url: str, tts_url: str) -> None:
        self._asr = AsrConfig(
            url=asr_url,
            model="qwen3-asr-flash-realtime",
            api_key="explicit-fake-protocol-key",
            language="zh",
            format="pcm",
            sample_rate=16000,
            enable_turn_detection=True,
            turn_detection_type="server_vad",
            turn_detection_threshold=0,
            turn_detection_silence_duration_ms=2000,
        )
        self._tts = TtsConfig(
            url=tts_url,
            model="qwen3-tts-flash-realtime",
            api_key="explicit-fake-protocol-key",
            voice="Cherry",
            format="pcm",
            sample_rate=24000,
            mode="commit",
            language_type="Chinese",
            speech_rate=1,
            volume=60,
        )

    async def asr_config(self, session_id: str) -> AsrConfig:
        del session_id
        return self._asr

    async def tts_config(self, session_id: str) -> TtsConfig:
        del session_id
        return self._tts


@pytest.mark.asyncio
async def test_dashscope_asr_adapter_sends_protocol_and_dispatches_text() -> None:
    received: list[dict[str, Any]] = []
    authorization: list[str | None] = []

    async def handler(connection: ServerConnection) -> None:
        authorization.append(connection.request.headers.get("Authorization"))
        async for raw in connection:
            assert isinstance(raw, str)
            message = json.loads(raw)
            received.append(message)
            if message["type"] == "input_audio_buffer.append":
                await connection.send(
                    json.dumps(
                        {
                            "type": ("conversation.item.input_audio_transcription.text"),
                            "text": "北京",
                            "stash": "天气",
                        }
                    )
                )
                await connection.send(
                    json.dumps(
                        {
                            "type": ("conversation.item.input_audio_transcription.completed"),
                            "transcript": "北京天气",
                        }
                    )
                )
            elif message["type"] == "session.finish":
                return

    server = await serve(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    config = StaticVoiceConfig(
        f"ws://127.0.0.1:{port}/asr",
        f"ws://127.0.0.1:{port}/tts",
    )
    ready = asyncio.Event()
    partials: list[str] = []
    finals: list[str] = []
    errors: list[Exception] = []
    provider = DashScopeAsrProvider(config)
    session = await provider.open(
        "1",
        on_ready=lambda: _set_event(ready),
        on_partial=lambda text: _append_text(partials, text),
        on_final=lambda text: _append_text(finals, text),
        on_error=lambda error: _append_error(errors, error),
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=1)
        await session.append_audio(b"pcm")
        await _wait_for(lambda: bool(finals))
    finally:
        await session.close()
        server.close()
        await server.wait_closed()

    assert authorization == ["Bearer explicit-fake-protocol-key"]
    assert received[0]["type"] == "session.update"
    assert received[0]["session"]["sample_rate"] == 16000
    assert received[1] == {
        "type": "input_audio_buffer.append",
        "audio": base64.b64encode(b"pcm").decode(),
    }
    assert partials == ["北京天气"]
    assert finals == ["北京天气"]
    assert errors == []


@pytest.mark.asyncio
async def test_dashscope_tts_adapter_collects_audio_delta() -> None:
    received: list[dict[str, Any]] = []

    async def handler(connection: ServerConnection) -> None:
        async for raw in connection:
            assert isinstance(raw, str)
            message = json.loads(raw)
            received.append(message)
            if message["type"] == "input_text_buffer.commit":
                await connection.send(
                    json.dumps(
                        {
                            "type": "response.audio.delta",
                            "delta": base64.b64encode(b"first").decode(),
                        }
                    )
                )
                await connection.send(
                    json.dumps(
                        {
                            "type": "response.audio.delta",
                            "audio": base64.b64encode(b"second").decode(),
                        }
                    )
                )
                await connection.send('{"type":"response.done"}')
            elif message["type"] == "session.finish":
                return

    server = await serve(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    config = StaticVoiceConfig(
        f"ws://127.0.0.1:{port}/asr",
        f"ws://127.0.0.1:{port}/tts",
    )
    synthesizer = DashScopeTtsSynthesizer(config, settings())
    try:
        audio = await synthesizer.synthesize("session-1", "测试语音")
    finally:
        server.close()
        await server.wait_closed()

    assert audio == b"firstsecond"
    assert [message["type"] for message in received[:3]] == [
        "session.update",
        "input_text_buffer.append",
        "input_text_buffer.commit",
    ]
    assert received[0]["session"]["sample_rate"] == 24000
    assert received[1]["text"] == "测试语音"


async def _set_event(event: asyncio.Event) -> None:
    event.set()


async def _append_text(values: list[str], text: str) -> None:
    values.append(text)


async def _append_error(values: list[Exception], error: Exception) -> None:
    values.append(error)


async def _wait_for(predicate: Any) -> None:
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not reached")
