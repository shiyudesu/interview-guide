from __future__ import annotations

from dataclasses import dataclass

import pytest

from interview_guide.common.redis.streams import (
    FIELD_SESSION_ID,
    FIELD_VOICE_SESSION_ID,
    INTERVIEW_EVALUATE,
    StreamMessage,
)
from interview_guide.modules.voice_interview.evaluation import VoiceEvaluateStreamHandler


class FakeRepository:
    async def find_session(self, session_id: int):
        return object() if session_id == 42 else None

    async def core_session_public_id(self, session_id: int) -> str | None:
        return "core-session" if session_id == 42 else None

    async def core_evaluate_status(self, session_id: int) -> str | None:
        del session_id
        return "PENDING"


class FakeStreams:
    def __init__(self) -> None:
        self.added: list[tuple[str, dict[str, str]]] = []

    async def add(self, key: str, fields: dict[str, str]) -> str:
        self.added.append((key, fields))
        return "1-0"


@dataclass
class FakeStatus:
    updates: list[tuple[int, str, str | None]]

    async def update_evaluate_status(
        self,
        session_id: int,
        status: str,
        error: str | None,
    ) -> None:
        self.updates.append((session_id, status, error))


@pytest.mark.asyncio
async def test_legacy_voice_stream_forwards_to_unified_evaluation() -> None:
    streams = FakeStreams()
    status = FakeStatus([])
    handler = VoiceEvaluateStreamHandler(
        FakeRepository(),  # type: ignore[arg-type]
        streams,  # type: ignore[arg-type]
        status,
    )
    payload = await handler.parse(StreamMessage("1-0", {FIELD_VOICE_SESSION_ID: "42"}))
    assert payload is not None
    assert await handler.try_mark_processing(payload)
    await handler.process(payload)
    await handler.mark_completed(payload)

    assert streams.added == [
        (INTERVIEW_EVALUATE.key, {FIELD_SESSION_ID: "core-session", "retryCount": "0"})
    ]
    assert status.updates == [(42, "PROCESSING", None), (42, "PENDING", None)]
