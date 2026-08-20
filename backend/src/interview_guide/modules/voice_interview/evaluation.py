from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from interview_guide.common.redis.streams import (
    FIELD_RETRY_COUNT,
    FIELD_SESSION_ID,
    FIELD_VOICE_SESSION_ID,
    INTERVIEW_EVALUATE,
    VOICE_EVALUATE,
    RedisStreamService,
    StreamMessage,
)
from interview_guide.modules.voice_interview.repository import VoiceInterviewRepository


class VoiceEvaluationStatusService(Protocol):
    async def update_evaluate_status(
        self,
        session_id: int,
        status: str,
        error: str | None,
    ) -> None: ...


@dataclass(frozen=True)
class VoiceEvaluatePayload:
    session_id: int


class VoiceEvaluateStreamHandler:
    """Drain the legacy voice stream into the unified interview evaluator."""

    def __init__(
        self,
        repository: VoiceInterviewRepository,
        streams: RedisStreamService,
        status_service: VoiceEvaluationStatusService,
    ) -> None:
        self._repository = repository
        self._streams = streams
        self._status_service = status_service

    async def parse(self, message: StreamMessage) -> VoiceEvaluatePayload | None:
        session_id = message.data.get(FIELD_VOICE_SESSION_ID)
        return VoiceEvaluatePayload(int(session_id)) if session_id is not None else None

    async def should_skip(self, payload: VoiceEvaluatePayload) -> bool:
        if await self._repository.find_session(payload.session_id) is None:
            return True
        return await self._repository.core_evaluate_status(payload.session_id) == "COMPLETED"

    async def try_mark_processing(self, payload: VoiceEvaluatePayload) -> bool:
        await self._status_service.update_evaluate_status(
            payload.session_id,
            "PROCESSING",
            None,
        )
        return True

    async def process(self, payload: VoiceEvaluatePayload) -> None:
        core_session_id = await self._repository.core_session_public_id(payload.session_id)
        if core_session_id is None:
            return
        await self._streams.add(
            INTERVIEW_EVALUATE.key,
            {FIELD_SESSION_ID: core_session_id, FIELD_RETRY_COUNT: "0"},
        )

    async def mark_completed(self, payload: VoiceEvaluatePayload) -> None:
        await self._status_service.update_evaluate_status(
            payload.session_id,
            "PENDING",
            None,
        )

    async def retry(self, payload: VoiceEvaluatePayload, retry_count: int) -> None:
        await self._streams.add(
            VOICE_EVALUATE.key,
            {
                FIELD_VOICE_SESSION_ID: str(payload.session_id),
                FIELD_RETRY_COUNT: str(retry_count),
            },
        )

    async def mark_failed(self, payload: VoiceEvaluatePayload, error: str) -> None:
        await self._status_service.update_evaluate_status(
            payload.session_id,
            "FAILED",
            error,
        )
