from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from redis.asyncio import Redis

from interview_guide.common.db.models import VoiceInterviewMessage, VoiceInterviewSession
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.redis.streams import (
    FIELD_RETRY_COUNT,
    FIELD_VOICE_SESSION_ID,
    VOICE_EVALUATE,
    RedisStreamService,
)
from interview_guide.modules.voice_interview.models import (
    CreateVoiceSessionRequest,
    VoiceInterviewMessageResponse,
    VoiceInterviewPhase,
    VoiceSessionMeta,
    VoiceSessionResponse,
    VoiceSessionStatus,
)
from interview_guide.modules.voice_interview.repository import (
    VoiceInterviewRepository,
)

logger = logging.getLogger(__name__)
SESSION_CACHE_KEY_PREFIX = "voice:interview:session:"
SESSION_CACHE_TTL_SECONDS = 60 * 60
DEFAULT_USER_ID = "default"
DEFAULT_SKILL_ID = "java-backend"
DEFAULT_DIFFICULTY = "mid"
STALE_SESSION_AGE = timedelta(hours=2)
PENDING_EVALUATION_REQUEUE_DELAY = timedelta(minutes=3)
PROCESSING_EVALUATION_TIMEOUT = timedelta(minutes=30)


class VoiceEvaluationProducer:
    def __init__(
        self,
        streams: RedisStreamService,
        repository: VoiceInterviewRepository,
        cache_redis: Redis,
    ) -> None:
        self._streams = streams
        self._repository = repository
        self._cache_redis = cache_redis

    async def send(self, session_id: int, retry_count: int = 0) -> bool:
        try:
            await self._streams.add(
                VOICE_EVALUATE.key,
                {
                    FIELD_VOICE_SESSION_ID: str(session_id),
                    FIELD_RETRY_COUNT: str(retry_count),
                },
            )
            logger.info(
                "voice evaluation task queued sessionId=%s retryCount=%s",
                session_id,
                retry_count,
            )
            return True
        except Exception as error:
            detail = f"任务入队失败: {error}"[:500]
            logger.exception("failed to queue voice evaluation sessionId=%s", session_id)
            await self._repository.update_evaluate_status(session_id, "FAILED", detail)
            await self._cache_redis.delete(f"{SESSION_CACHE_KEY_PREFIX}{session_id}")
            return False


class VoiceInterviewService:
    def __init__(
        self,
        repository: VoiceInterviewRepository,
        cache_redis: Redis,
        producer: VoiceEvaluationProducer,
        now: Callable[[], datetime],
    ) -> None:
        self.repository = repository
        self._redis = cache_redis
        self._producer = producer
        self._now = now

    async def create_session(
        self,
        request: CreateVoiceSessionRequest,
    ) -> VoiceSessionResponse:
        skill_id = request.skill_id if request.skill_id is not None else DEFAULT_SKILL_ID
        llm_provider = (
            request.llm_provider
            if request.llm_provider is not None and request.llm_provider.strip()
            else None
        )
        entity = await self.repository.create_session(
            role_type=skill_id,
            skill_id=skill_id,
            difficulty=(
                request.difficulty if request.difficulty is not None else DEFAULT_DIFFICULTY
            ),
            custom_jd_text=request.custom_jd_text,
            resume_id=request.resume_id,
            intro_enabled=request.intro_enabled,
            tech_enabled=request.tech_enabled,
            project_enabled=request.project_enabled,
            hr_enabled=request.hr_enabled,
            llm_provider=llm_provider,
            planned_duration=request.planned_duration,
            current_phase=self._first_phase(request),
        )
        await self._cache_session(entity)
        return self._response(entity)

    async def get_session(self, session_id: int | None) -> VoiceInterviewSession | None:
        if session_id is None:
            return None
        cached = await self._redis.get(self._cache_key(session_id))
        if cached is not None:
            try:
                return self._session_from_cache(json.loads(cached))
            except (TypeError, ValueError, json.JSONDecodeError):
                logger.warning("invalid voice session cache sessionId=%s", session_id)
        return await self.repository.find_session(session_id)

    async def get_session_response(self, session_id: int) -> VoiceSessionResponse | None:
        entity = await self.get_session(session_id)
        return self._response(entity) if entity is not None else None

    async def list_sessions(
        self,
        user_id: str | None,
        status: str | None,
    ) -> list[VoiceSessionMeta]:
        normalized_status: str | None = None
        if status is not None and status:
            normalized_status = VoiceSessionStatus(status.upper()).value
        rows = await self.repository.list_sessions(
            user_id if user_id is not None else DEFAULT_USER_ID,
            normalized_status,
        )
        return [
            VoiceSessionMeta(
                session_id=row.session.id,
                role_type=row.session.role_type,
                status=str(row.session.status),
                current_phase=str(row.session.current_phase),
                created_at=row.session.created_at,
                updated_at=row.session.updated_at,
                actual_duration=row.session.actual_duration,
                message_count=row.message_count,
                evaluate_status=row.session.evaluate_status,
                evaluate_error=row.session.evaluate_error,
            )
            for row in rows
        ]

    async def end_session(
        self,
        session_id: int,
        *,
        only_if_in_progress: bool = False,
    ) -> bool:
        entity = await self.repository.end_session(
            session_id,
            only_if_in_progress=only_if_in_progress,
        )
        if entity is None:
            return False
        await self._invalidate_cache(session_id)
        await self._producer.send(session_id)
        return True

    async def pause_session(self, session_id: int, reason: str) -> None:
        entity = await self.repository.find_session(session_id)
        if entity is None:
            raise BusinessException(ErrorCode.NOT_FOUND, f"会话不存在: {session_id}")
        if entity.status != VoiceSessionStatus.IN_PROGRESS:
            raise BusinessException(
                ErrorCode.BAD_REQUEST,
                f"会话状态为 {entity.status}，无法暂停",
            )
        await self.repository.pause_session(session_id)
        await self._invalidate_cache(session_id)
        logger.info("voice session paused sessionId=%s reason=%s", session_id, reason)

    async def resume_session(self, session_id: int) -> VoiceSessionResponse:
        entity = await self.repository.find_session(session_id)
        if entity is None:
            raise BusinessException(ErrorCode.NOT_FOUND, f"会话不存在: {session_id}")
        if entity.status != VoiceSessionStatus.PAUSED:
            raise BusinessException(
                ErrorCode.BAD_REQUEST,
                f"会话状态为 {entity.status}，无法恢复",
            )
        resumed = await self.repository.resume_session(session_id)
        assert resumed is not None
        await self._cache_session(resumed)
        return self._response(resumed)

    async def start_phase(self, session_id: int, phase: str | None) -> None:
        if phase is None:
            return
        try:
            normalized = VoiceInterviewPhase(phase.upper()).value
        except ValueError:
            logger.exception("invalid voice phase phase=%s", phase)
            return
        updated = await self.repository.update_phase(session_id, normalized)
        if updated is not None:
            await self._cache_session(updated)

    async def messages(self, session_id: int) -> list[VoiceInterviewMessageResponse]:
        return [self._message_response(item) for item in await self.repository.messages(session_id)]

    async def history(self, session_id: int) -> list[VoiceInterviewMessage]:
        return await self.repository.messages(session_id)

    async def save_message(
        self,
        session_id: int,
        user_text: str | None,
        ai_text: str | None,
    ) -> None:
        await self.repository.save_message(session_id, user_text, ai_text)

    async def delete_session(self, session_id: int) -> None:
        if not await self.repository.delete_session(session_id):
            raise BusinessException(
                ErrorCode.VOICE_SESSION_NOT_FOUND,
                f"会话不存在: {session_id}",
            )
        await self._invalidate_cache(session_id)

    async def trigger_evaluation(self, session_id: int) -> None:
        await self.update_evaluate_status(session_id, "PENDING", None)
        await self._producer.send(session_id)

    async def update_evaluate_status(
        self,
        session_id: int,
        status: str,
        error: str | None,
    ) -> None:
        try:
            await self.repository.update_evaluate_status(session_id, status, error)
            await self._invalidate_cache(session_id)
        except Exception:
            logger.exception(
                "failed to update voice evaluation status sessionId=%s status=%s",
                session_id,
                status,
            )

    async def cleanup_stale_sessions(self) -> int:
        now = self._now()
        cleaned = 0
        for entity in await self.repository.stale_in_progress(now - STALE_SESSION_AGE):
            if await self.end_session(entity.id):
                cleaned += 1
        for entity in await self.repository.stale_evaluations(
            "PENDING",
            now - PENDING_EVALUATION_REQUEUE_DELAY,
        ):
            await self.update_evaluate_status(entity.id, "PENDING", None)
            await self._producer.send(entity.id)
            cleaned += 1
        for entity in await self.repository.stale_evaluations(
            "PROCESSING",
            now - PROCESSING_EVALUATION_TIMEOUT,
        ):
            await self.update_evaluate_status(
                entity.id,
                "FAILED",
                "评估超时，请重新触发",
            )
            cleaned += 1
        return cleaned

    async def _cache_session(self, entity: VoiceInterviewSession) -> None:
        await self._redis.set(
            self._cache_key(entity.id),
            json.dumps(
                self._session_cache_document(entity),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            ex=SESSION_CACHE_TTL_SECONDS,
        )

    async def _invalidate_cache(self, session_id: int) -> None:
        await self._redis.delete(self._cache_key(session_id))

    @staticmethod
    def _cache_key(session_id: int) -> str:
        return f"{SESSION_CACHE_KEY_PREFIX}{session_id}"

    @staticmethod
    def _first_phase(request: CreateVoiceSessionRequest) -> str:
        if request.intro_enabled:
            return "INTRO"
        if request.tech_enabled:
            return "TECH"
        if request.project_enabled:
            return "PROJECT"
        if request.hr_enabled:
            return "HR"
        return "COMPLETED"

    @staticmethod
    def _response(entity: VoiceInterviewSession) -> VoiceSessionResponse:
        return VoiceSessionResponse(
            session_id=entity.id,
            role_type=entity.role_type,
            current_phase=str(entity.current_phase),
            status=str(entity.status),
            start_time=entity.start_time,
            planned_duration=entity.planned_duration,
            web_socket_url=(f"ws://localhost:8080/ws/voice-interview/{entity.id}"),
        )

    @staticmethod
    def _message_response(
        entity: VoiceInterviewMessage,
    ) -> VoiceInterviewMessageResponse:
        return VoiceInterviewMessageResponse(
            id=entity.id,
            session_id=entity.session_id,
            message_type=entity.message_type,
            phase=entity.phase,
            user_recognized_text=entity.user_recognized_text,
            ai_generated_text=entity.ai_generated_text,
            timestamp=entity.timestamp,
            sequence_num=entity.sequence_num,
        )

    @staticmethod
    def _session_cache_document(entity: VoiceInterviewSession) -> dict[str, Any]:
        def timestamp(value: datetime | None) -> str | None:
            return value.isoformat() if value is not None else None

        return {
            "id": entity.id,
            "actual_duration": entity.actual_duration,
            "created_at": timestamp(entity.created_at),
            "current_phase": entity.current_phase,
            "custom_jd_text": entity.custom_jd_text,
            "difficulty": entity.difficulty,
            "end_time": timestamp(entity.end_time),
            "evaluate_error": entity.evaluate_error,
            "evaluate_status": entity.evaluate_status,
            "hr_enabled": entity.hr_enabled,
            "intro_enabled": entity.intro_enabled,
            "llm_provider": entity.llm_provider,
            "paused_at": timestamp(entity.paused_at),
            "planned_duration": entity.planned_duration,
            "project_enabled": entity.project_enabled,
            "resume_id": entity.resume_id,
            "resumed_at": timestamp(entity.resumed_at),
            "role_type": entity.role_type,
            "skill_id": entity.skill_id,
            "start_time": timestamp(entity.start_time),
            "status": entity.status,
            "tech_enabled": entity.tech_enabled,
            "updated_at": timestamp(entity.updated_at),
            "user_id": entity.user_id,
        }

    @staticmethod
    def _session_from_cache(document: dict[str, Any]) -> VoiceInterviewSession:
        def timestamp(key: str) -> datetime | None:
            value = document.get(key)
            return datetime.fromisoformat(value) if isinstance(value, str) else None

        return VoiceInterviewSession(
            id=int(document["id"]),
            actual_duration=document.get("actual_duration"),
            created_at=timestamp("created_at"),
            current_phase=document.get("current_phase"),
            custom_jd_text=document.get("custom_jd_text"),
            difficulty=document.get("difficulty"),
            end_time=timestamp("end_time"),
            evaluate_error=document.get("evaluate_error"),
            evaluate_status=document.get("evaluate_status"),
            hr_enabled=document.get("hr_enabled"),
            intro_enabled=document.get("intro_enabled"),
            llm_provider=document.get("llm_provider"),
            paused_at=timestamp("paused_at"),
            planned_duration=document.get("planned_duration"),
            project_enabled=document.get("project_enabled"),
            resume_id=document.get("resume_id"),
            resumed_at=timestamp("resumed_at"),
            role_type=str(document["role_type"]),
            skill_id=document.get("skill_id"),
            start_time=timestamp("start_time"),
            status=document.get("status"),
            tech_enabled=document.get("tech_enabled"),
            updated_at=timestamp("updated_at"),
            user_id=document.get("user_id"),
        )
