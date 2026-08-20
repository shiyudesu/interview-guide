from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Iterable

from interview_guide.modules.voice_interview.protocols import (
    AsrAppendError,
    AsrErrorCallback,
    AsrNotReadyError,
    AsrReadyCallback,
    AsrTextCallback,
    VoiceAsrProvider,
    VoiceAsrSession,
)


class ExplicitFakeAsrSession(VoiceAsrSession):
    def __init__(
        self,
        *,
        on_ready: AsrReadyCallback,
        on_partial: AsrTextCallback,
        on_final: AsrTextCallback,
        on_error: AsrErrorCallback,
        append_failures: Iterable[bool] = (),
        ready_on_open: bool = True,
    ) -> None:
        self._on_ready = on_ready
        self._on_partial = on_partial
        self._on_final = on_final
        self._on_error = on_error
        self._append_failures = deque(append_failures)
        self._ready = False
        self._closed = False
        self._ready_on_open = ready_on_open
        self.appended_audio: list[bytes] = []
        self.restart_count = 0
        self.close_count = 0

    @property
    def ready(self) -> bool:
        return self._ready

    def start(self) -> None:
        if self._ready_on_open:
            asyncio.get_running_loop().call_soon(lambda: asyncio.create_task(self.mark_ready()))

    async def mark_ready(self) -> None:
        if self._closed:
            return
        self._ready = True
        await self._on_ready()

    async def emit_partial(self, text: str) -> None:
        await self._on_partial(text)

    async def emit_final(self, text: str) -> None:
        await self._on_final(text)

    async def emit_error(self, error: Exception) -> None:
        await self._on_error(error)

    async def append_audio(self, audio: bytes) -> None:
        if self._closed:
            raise AsrAppendError("No active session")
        if not self._ready:
            raise AsrNotReadyError("ASR session not ready")
        if self._append_failures and self._append_failures.popleft():
            raise AsrAppendError("ASR append failed")
        self.appended_audio.append(audio)

    async def restart(self) -> None:
        self.restart_count += 1
        self._ready = True
        await self._on_ready()

    async def close(self) -> None:
        self.close_count += 1
        self._closed = True
        self._ready = False


class ExplicitFakeAsrProvider(VoiceAsrProvider):
    def __init__(
        self,
        *,
        append_failures: Iterable[bool] = (),
        ready_on_open: bool = True,
    ) -> None:
        self._append_failures = tuple(append_failures)
        self._ready_on_open = ready_on_open
        self.sessions: list[ExplicitFakeAsrSession] = []

    async def open(
        self,
        session_id: str,
        *,
        on_ready: AsrReadyCallback,
        on_partial: AsrTextCallback,
        on_final: AsrTextCallback,
        on_error: AsrErrorCallback,
    ) -> ExplicitFakeAsrSession:
        del session_id
        session = ExplicitFakeAsrSession(
            on_ready=on_ready,
            on_partial=on_partial,
            on_final=on_final,
            on_error=on_error,
            append_failures=self._append_failures,
            ready_on_open=self._ready_on_open,
        )
        self.sessions.append(session)
        session.start()
        return session


class ExplicitFakeTtsSynthesizer:
    def __init__(
        self,
        audio_by_text: dict[str, bytes] | None = None,
        *,
        delay_seconds: float = 0,
    ) -> None:
        self._audio_by_text = audio_by_text or {}
        self._delay_seconds = delay_seconds
        self.calls: list[str] = []
        self.active = 0
        self.max_active = 0
        self.cancelled = 0

    async def synthesize(self, text: str) -> bytes:
        self.calls.append(text)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self._delay_seconds:
                await asyncio.sleep(self._delay_seconds)
            else:
                await asyncio.sleep(0)
            return self._audio_by_text.get(text, text.encode())
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        finally:
            self.active -= 1
