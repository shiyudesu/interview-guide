from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, dataclass, replace
from urllib.parse import urlsplit

from interview_guide.common.config.settings import Settings
from interview_guide.modules.llm_provider.models import (
    AsrConfigRequest,
    AsrConfigResponse,
    ProviderTestResult,
    TtsConfigRequest,
    TtsConfigResponse,
)
from interview_guide.modules.llm_provider.service import mask_api_key


@dataclass(frozen=True)
class AsrConfig:
    url: str
    model: str
    api_key: str
    language: str
    format: str
    sample_rate: int
    enable_turn_detection: bool
    turn_detection_type: str
    turn_detection_threshold: float
    turn_detection_silence_duration_ms: int


@dataclass(frozen=True)
class TtsConfig:
    model: str
    api_key: str
    voice: str
    format: str
    sample_rate: int
    mode: str
    language_type: str
    speech_rate: float
    volume: int


class VoiceConfigStore:
    def __init__(self, settings: Settings) -> None:
        self._path = settings.voice_config_path.expanduser()
        api_key = settings.ai_bailian_api_key.get_secret_value()
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
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if not self._path.is_file():
            return
        document = json.loads(await asyncio.to_thread(self._path.read_text, encoding="utf-8"))
        self._asr = AsrConfig(**document["asr"])
        self._tts = TtsConfig(**document["tts"])

    async def asr(self) -> AsrConfigResponse:
        async with self._lock:
            return AsrConfigResponse(
                url=self._asr.url,
                model=self._asr.model,
                masked_api_key=mask_api_key(self._asr.api_key),
                language=self._asr.language,
                format=self._asr.format,
                sample_rate=self._asr.sample_rate,
                enable_turn_detection=self._asr.enable_turn_detection,
                turn_detection_type=self._asr.turn_detection_type,
                turn_detection_threshold=self._asr.turn_detection_threshold,
                turn_detection_silence_duration_ms=(self._asr.turn_detection_silence_duration_ms),
            )

    async def tts(self) -> TtsConfigResponse:
        async with self._lock:
            return TtsConfigResponse(
                model=self._tts.model,
                masked_api_key=mask_api_key(self._tts.api_key),
                voice=self._tts.voice,
                format=self._tts.format,
                sample_rate=self._tts.sample_rate,
                mode=self._tts.mode,
                language_type=self._tts.language_type,
                speech_rate=self._tts.speech_rate,
                volume=self._tts.volume,
            )

    async def update_asr(self, request: AsrConfigRequest) -> None:
        async with self._lock:
            api_key = request.api_key
            self._asr = replace(
                self._asr,
                url=request.url if request.url is not None else self._asr.url,
                model=(request.model if request.model is not None else self._asr.model),
                api_key=api_key if api_key is not None else self._asr.api_key,
                language=(request.language if request.language is not None else self._asr.language),
                format=(request.format if request.format is not None else self._asr.format),
                sample_rate=(
                    request.sample_rate
                    if request.sample_rate is not None
                    else self._asr.sample_rate
                ),
                enable_turn_detection=(
                    request.enable_turn_detection
                    if request.enable_turn_detection is not None
                    else self._asr.enable_turn_detection
                ),
                turn_detection_type=(
                    request.turn_detection_type
                    if request.turn_detection_type is not None
                    else self._asr.turn_detection_type
                ),
                turn_detection_threshold=(
                    request.turn_detection_threshold
                    if request.turn_detection_threshold is not None
                    else self._asr.turn_detection_threshold
                ),
                turn_detection_silence_duration_ms=(
                    request.turn_detection_silence_duration_ms
                    if request.turn_detection_silence_duration_ms is not None
                    else self._asr.turn_detection_silence_duration_ms
                ),
            )
            if api_key is not None:
                self._tts = replace(self._tts, api_key=api_key)
            await self._persist()

    async def update_tts(self, request: TtsConfigRequest) -> None:
        async with self._lock:
            api_key = request.api_key
            self._tts = replace(
                self._tts,
                model=(request.model if request.model is not None else self._tts.model),
                api_key=api_key if api_key is not None else self._tts.api_key,
                voice=(request.voice if request.voice is not None else self._tts.voice),
                format=(request.format if request.format is not None else self._tts.format),
                sample_rate=(
                    request.sample_rate
                    if request.sample_rate is not None
                    else self._tts.sample_rate
                ),
                mode=(request.mode if request.mode is not None else self._tts.mode),
                language_type=(
                    request.language_type
                    if request.language_type is not None
                    else self._tts.language_type
                ),
                speech_rate=(
                    request.speech_rate
                    if request.speech_rate is not None
                    else self._tts.speech_rate
                ),
                volume=(request.volume if request.volume is not None else self._tts.volume),
            )
            if api_key is not None:
                self._asr = replace(self._asr, api_key=api_key)
            await self._persist()

    async def test_asr(self) -> ProviderTestResult:
        async with self._lock:
            config = self._asr
        try:
            uri = urlsplit(config.url)
            if uri.hostname is None:
                raise ValueError("URI host is missing")
            port = uri.port or (443 if uri.scheme == "wss" else 80)
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(uri.hostname, port),
                timeout=5,
            )
            writer.close()
            await writer.wait_closed()
            return ProviderTestResult(
                success=True,
                message=f"ASR WebSocket 连接成功: {uri.hostname}",
                model=config.model,
            )
        except Exception as error:
            return ProviderTestResult(
                success=False,
                message=f"ASR 连接失败: {error}",
                model=config.model,
            )

    async def _persist(self) -> None:
        document = json.dumps(
            {"asr": asdict(self._asr), "tts": asdict(self._tts)},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        await asyncio.to_thread(self._write_atomic, document)

    def _write_atomic(self, document: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temporary.write_text(document, encoding="utf-8")
        os.replace(temporary, self._path)
