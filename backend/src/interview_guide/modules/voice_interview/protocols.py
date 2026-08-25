from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

AsrReadyCallback = Callable[[], Awaitable[None]]
AsrTextCallback = Callable[[str], Awaitable[None]]
AsrErrorCallback = Callable[[Exception], Awaitable[None]]


class AsrNotReadyError(RuntimeError):
    pass


class AsrAppendError(RuntimeError):
    pass


class VoiceAsrSession(Protocol):
    @property
    def ready(self) -> bool: ...

    async def append_audio(self, audio: bytes) -> None: ...

    async def restart(self) -> None: ...

    async def close(self) -> None: ...


class VoiceAsrProvider(Protocol):
    async def open(
        self,
        session_id: str,
        *,
        on_ready: AsrReadyCallback,
        on_partial: AsrTextCallback,
        on_final: AsrTextCallback,
        on_error: AsrErrorCallback,
    ) -> VoiceAsrSession: ...


class VoiceTtsSynthesizer(Protocol):
    async def synthesize(self, session_id: str, text: str) -> bytes: ...


class VoiceClock(Protocol):
    def now_ms(self) -> int: ...

    async def sleep(self, seconds: float) -> None: ...
