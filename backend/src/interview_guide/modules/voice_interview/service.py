from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from interview_guide.common.ai.user_providers import normalize_provider_alias
from interview_guide.common.db.models import (
    LEGACY_OWNER_ID,
    VoiceInterviewMessage,
    VoiceInterviewSession,
)
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.modules.interview.models import (
    InterviewChannel,
    InterviewReportDTO,
    InterviewSessionDTO,
    PlannedInterviewQuestion,
    SubmitTurnRequest,
    SubmitTurnResponse,
)
from interview_guide.modules.interview.service import InterviewService
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
DEFAULT_USER_ID = LEGACY_OWNER_ID
DEFAULT_SKILL_ID = "java-backend"
DEFAULT_DIFFICULTY = "mid"
STALE_SESSION_AGE = timedelta(hours=2)


class VoiceInterviewService:
    def __init__(
        self,
        repository: VoiceInterviewRepository,
        cache_redis: Redis,
        interview_service: InterviewService,
        now: Callable[[], datetime],
        user_id: UUID | None = None,
    ) -> None:
        self.repository = repository
        self._redis = cache_redis
        self._interview = interview_service
        self._now = now
        self._user_id = user_id

    async def create_session(
        self,
        request: CreateVoiceSessionRequest,
    ) -> VoiceSessionResponse:
        if request.request_id is not None:
            existing_core = await self._interview.find_by_request_id(request.request_id)
            if existing_core is not None:
                existing_voice = await self.repository.find_by_core_public_id(
                    existing_core.session_id
                )
                if existing_voice is not None:
                    return self._response(existing_voice, existing_core.session_id)
        skill_id = request.skill_id if request.skill_id is not None else DEFAULT_SKILL_ID
        llm_provider = normalize_provider_alias(request.llm_provider)
        duration = request.planned_duration or 30
        phases = self._question_phases(request, duration // 5)
        questions = await self._voice_questions(
            request,
            phases,
            skill_id,
            llm_provider,
        )
        core = await self._interview.create_session_from_questions(
            questions,
            channel=InterviewChannel.VOICE,
            max_follow_ups_per_main=self._interview.follow_up_count,
            llm_provider=llm_provider,
            skill_id=skill_id,
            difficulty=request.difficulty or DEFAULT_DIFFICULTY,
            request_id=request.request_id,
            resume_id=request.resume_id,
            context={
                "customJdText": request.custom_jd_text or "",
                "plannedDuration": duration,
                "phases": phases,
            },
        )
        existing_voice = await self.repository.find_by_core_public_id(core.session_id)
        if existing_voice is not None:
            return self._response(existing_voice, core.session_id)
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
            planned_duration=duration,
            current_phase=phases[0],
            interview_session_public_id=core.session_id,
        )
        await self._cache_session(entity)
        return self._response(entity, core.session_id)

    async def get_session(self, session_id: int | None) -> VoiceInterviewSession | None:
        if session_id is None:
            return None
        cached = (
            await self._redis.get(self._cache_key(session_id, self._user_id))
            if self._user_id is not None
            else None
        )
        if cached is not None:
            try:
                entity = self._session_from_cache(json.loads(cached))
                if self._user_id is None or entity.user_id == self._user_id:
                    return entity
            except (TypeError, ValueError, json.JSONDecodeError):
                logger.warning("invalid voice session cache sessionId=%s", session_id)
        return await self.repository.find_session(session_id)

    async def get_session_response(self, session_id: int) -> VoiceSessionResponse | None:
        entity = await self.get_session(session_id)
        if entity is None:
            return None
        core_id = await self.repository.core_session_public_id(session_id)
        return self._response(entity, core_id)

    async def list_sessions(
        self,
        user_id: UUID | None,
        status: str | None,
        *,
        session_ids: list[int] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[VoiceSessionMeta]:
        normalized_status: str | None = None
        if status is not None and status:
            normalized_status = VoiceSessionStatus(status.upper()).value
        rows = await self.repository.list_sessions(
            user_id if user_id is not None else DEFAULT_USER_ID,
            normalized_status,
            session_ids=session_ids,
            limit=limit,
            offset=offset,
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
                evaluate_status=row.evaluate_status,
                evaluate_error=row.evaluate_error,
                overall_score=row.overall_score,
            )
            for row in rows
        ]

    async def end_session(
        self,
        session_id: int,
        *,
        only_if_in_progress: bool = False,
    ) -> bool:
        core_id = await self.repository.core_session_public_id(session_id)
        entity = await self.repository.end_session(
            session_id,
            only_if_in_progress=only_if_in_progress,
        )
        if entity is None:
            return False
        await self._invalidate_cache(session_id, entity.user_id)
        if core_id is not None:
            await self._interview.complete(core_id)
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
        await self._invalidate_cache(session_id, entity.user_id)
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
        return self._response(
            resumed,
            await self.repository.core_session_public_id(session_id),
        )

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
        if await self.get_session(session_id) is None:
            raise BusinessException(ErrorCode.VOICE_SESSION_NOT_FOUND)
        return [self._message_response(item) for item in await self.repository.messages(session_id)]

    async def history(self, session_id: int) -> list[VoiceInterviewMessage]:
        return await self.repository.messages(session_id)

    async def save_message(
        self,
        session_id: int,
        user_text: str | None,
        ai_text: str | None,
        interview_turn_id: UUID | None = None,
    ) -> None:
        await self.repository.save_message(
            session_id,
            user_text,
            ai_text,
            interview_turn_id,
        )

    async def core_session(self, session_id: int) -> InterviewSessionDTO:
        core_id = await self.repository.core_session_public_id(session_id)
        if core_id is None:
            raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)
        return await self._interview.get_session(core_id)

    async def submit_turn(
        self,
        session_id: int,
        request_id: str,
        answer: str,
    ) -> SubmitTurnResponse:
        voice = await self.get_session(session_id)
        if voice is None:
            raise BusinessException(ErrorCode.VOICE_SESSION_NOT_FOUND)
        core_id = await self.repository.core_session_public_id(session_id)
        if core_id is None:
            raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)
        core = await self._interview.get_session(core_id)
        if core.current_question is None:
            raise BusinessException(ErrorCode.INTERVIEW_ALREADY_COMPLETED)
        elapsed = int((self._now() - (voice.start_time or self._now())).total_seconds())
        remaining = max(0, int((voice.planned_duration or 0) * 60) - elapsed)
        response = await self._interview.submit_turn(
            core_id,
            SubmitTurnRequest(
                request_id=request_id,
                question_id=core.current_question.question_id,
                answer=answer,
            ),
            remaining_seconds=remaining,
        )
        if response.next_question is not None and response.next_question.phase is not None:
            await self.start_phase(session_id, response.next_question.phase)
        if response.completed:
            await self.repository.end_session(session_id, only_if_in_progress=False)
            await self._invalidate_cache(session_id, voice.user_id)
        return response

    async def evaluation_report(self, session_id: int) -> InterviewReportDTO | None:
        core_id = await self.repository.core_session_public_id(session_id)
        if core_id is None:
            return None
        try:
            return await self._interview.report(core_id)
        except BusinessException:
            return None

    async def delete_session(self, session_id: int) -> None:
        entity = await self.repository.find_session(session_id)
        if entity is None:
            raise BusinessException(
                ErrorCode.VOICE_SESSION_NOT_FOUND,
                f"会话不存在: {session_id}",
            )
        core_id = await self.repository.core_session_public_id(session_id)
        if not await self.repository.delete_session(session_id):
            raise BusinessException(
                ErrorCode.VOICE_SESSION_NOT_FOUND,
                f"会话不存在: {session_id}",
            )
        await self._invalidate_cache(session_id, entity.user_id)
        if core_id is not None:
            await self._interview.delete(core_id)

    async def trigger_evaluation(self, session_id: int) -> None:
        core_id = await self.repository.core_session_public_id(session_id)
        if core_id is None:
            raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)
        await self.update_evaluate_status(session_id, "PENDING", None)
        await self._interview.regenerate_report(core_id)

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
        return cleaned

    async def _cache_session(self, entity: VoiceInterviewSession) -> None:
        await self._redis.set(
            self._cache_key(entity.id, entity.user_id),
            json.dumps(
                self._session_cache_document(entity),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            ex=SESSION_CACHE_TTL_SECONDS,
        )

    async def _invalidate_cache(
        self,
        session_id: int,
        user_id: UUID | None = None,
    ) -> None:
        owner = user_id or self._user_id
        if owner is not None:
            await self._redis.delete(self._cache_key(session_id, owner))

    @staticmethod
    def _cache_key(session_id: int, owner: UUID | None = None) -> str:
        owner = owner or LEGACY_OWNER_ID
        return f"{SESSION_CACHE_KEY_PREFIX}{owner}:{session_id}"

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
    def _response(
        entity: VoiceInterviewSession,
        core_session_id: str | None,
    ) -> VoiceSessionResponse:
        return VoiceSessionResponse(
            session_id=entity.id,
            interview_session_id=core_session_id,
            role_type=entity.role_type,
            current_phase=str(entity.current_phase),
            status=str(entity.status),
            start_time=entity.start_time,
            planned_duration=entity.planned_duration,
            web_socket_url=f"/ws/voice-interview/{entity.id}",
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
            "interview_session_id": entity.interview_session_id,
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
            "user_id": str(entity.user_id),
        }

    @staticmethod
    def _session_from_cache(document: dict[str, Any]) -> VoiceInterviewSession:
        def timestamp(key: str) -> datetime | None:
            value = document.get(key)
            return datetime.fromisoformat(value) if isinstance(value, str) else None

        return VoiceInterviewSession(
            id=int(document["id"]),
            interview_session_id=int(document["interview_session_id"]),
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
            user_id=UUID(str(document.get("user_id", LEGACY_OWNER_ID))),
        )

    @staticmethod
    def _question_phases(
        request: CreateVoiceSessionRequest,
        main_count: int,
    ) -> list[str]:
        enabled = [
            phase
            for phase, active in (
                ("INTRO", request.intro_enabled),
                ("TECH", request.tech_enabled),
                ("PROJECT", request.project_enabled),
                ("HR", request.hr_enabled),
            )
            if active
        ]
        total = max(main_count, len(enabled))
        allocations = {phase: 1 for phase in enabled}
        remaining = total - len(enabled)
        weighted = [phase for phase in ("TECH", "PROJECT", "HR") if phase in enabled]
        if not weighted:
            allocations[enabled[0]] += remaining
        else:
            weights = {"TECH": 5, "PROJECT": 3, "HR": 2}
            for _ in range(remaining):
                selected = min(
                    weighted,
                    key=lambda phase: allocations[phase] / weights[phase],
                )
                allocations[selected] += 1
        return [
            phase
            for phase in ("INTRO", "TECH", "PROJECT", "HR")
            for _ in range(allocations.get(phase, 0))
        ]

    async def _voice_questions(
        self,
        request: CreateVoiceSessionRequest,
        phases: list[str],
        skill_id: str,
        provider_id: str | None,
    ) -> list[PlannedInterviewQuestion]:
        difficulty = request.difficulty or DEFAULT_DIFFICULTY
        questions: list[PlannedInterviewQuestion] = []
        intro_count = phases.count("INTRO")
        intro_questions = (
            "请用一分钟做一个与本岗位相关的自我介绍。",
            "你希望面试官重点了解你哪一段经历？请说明原因。",
            "请概括你目前最有代表性的能力和一个证明它的案例。",
        )
        questions.extend(
            PlannedInterviewQuestion(
                question=intro_questions[index % len(intro_questions)],
                type="INTRO",
                category="自我介绍",
                topic_summary="岗位自我介绍",
                phase="INTRO",
            )
            for index in range(intro_count)
        )
        tech_count = phases.count("TECH")
        if tech_count:
            technical = await self._interview.generate_main_questions(
                provider_id=provider_id,
                skill_id=skill_id,
                difficulty=difficulty,
                resume_id=request.resume_id,
                resume_text="",
                question_count=tech_count,
                jd_text=request.custom_jd_text,
            )
            questions.extend(
                question.model_copy(update={"phase": "TECH"}) for question in technical
            )
        project_count = phases.count("PROJECT")
        if project_count:
            project = await self._interview.generate_main_questions(
                provider_id=provider_id,
                skill_id=skill_id,
                difficulty=difficulty,
                resume_id=request.resume_id,
                resume_text=None,
                question_count=project_count,
                jd_text=request.custom_jd_text,
            )
            questions.extend(
                question.model_copy(update={"phase": "PROJECT"}) for question in project
            )
        hr_questions = (
            "请分享一次你与团队成员产生分歧的经历，以及你是如何推动问题解决的？",
            "你选择下一份工作时最看重哪些因素？为什么？",
            "请介绍一次你面对高压力任务时进行优先级取舍的经历。",
        )
        for index in range(phases.count("HR")):
            questions.append(
                PlannedInterviewQuestion(
                    question=hr_questions[index % len(hr_questions)],
                    type="HR",
                    category="HR问题",
                    topic_summary="行为与职业动机",
                    phase="HR",
                )
            )
        return questions
