from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.db.models import (
    InterviewSession,
    Resume,
    VoiceInterviewMessage,
    VoiceInterviewSession,
)

SUMMARY_MESSAGE_TYPE = "SUMMARY"
DIALOGUE_MESSAGE_TYPE = "DIALOGUE"


def trim_to_none(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()


@dataclass(frozen=True)
class VoiceSessionListRow:
    session: VoiceInterviewSession
    message_count: int
    evaluate_status: str | None
    evaluate_error: str | None
    overall_score: int | None


class VoiceInterviewRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime],
    ) -> None:
        self._sessions = sessions
        self._now = now

    async def create_session(
        self,
        *,
        role_type: str,
        skill_id: str,
        difficulty: str,
        custom_jd_text: str | None,
        resume_id: int | None,
        intro_enabled: bool | None,
        tech_enabled: bool | None,
        project_enabled: bool | None,
        hr_enabled: bool | None,
        llm_provider: str | None,
        planned_duration: int | None,
        current_phase: str,
        interview_session_public_id: str,
    ) -> VoiceInterviewSession:
        timestamp = self._now()
        async with self._sessions() as session, session.begin():
            interview_session_id = await session.scalar(
                select(InterviewSession.id).where(
                    InterviewSession.session_id == interview_session_public_id
                )
            )
            if interview_session_id is None:
                raise LookupError(
                    f"核心面试会话不存在: {interview_session_public_id}"
                )
            entity = VoiceInterviewSession(
                actual_duration=None,
                created_at=timestamp,
                current_phase=current_phase,
                custom_jd_text=custom_jd_text,
                difficulty=difficulty,
                end_time=None,
                evaluate_error=None,
                evaluate_status=None,
                hr_enabled=hr_enabled,
                interview_session_id=interview_session_id,
                intro_enabled=intro_enabled,
                llm_provider=llm_provider,
                paused_at=None,
                planned_duration=planned_duration,
                project_enabled=project_enabled,
                resume_id=resume_id,
                resumed_at=None,
                role_type=role_type,
                skill_id=skill_id,
                start_time=timestamp,
                status="IN_PROGRESS",
                tech_enabled=tech_enabled,
                updated_at=timestamp,
                user_id="default",
            )
            session.add(entity)
            await session.flush()
            return entity

    async def find_session(self, session_id: int | None) -> VoiceInterviewSession | None:
        if session_id is None:
            return None
        async with self._sessions() as session:
            return await session.get(VoiceInterviewSession, session_id)

    async def resume_text(self, resume_id: int | None) -> str | None:
        if resume_id is None:
            return None
        async with self._sessions() as session:
            value = await session.scalar(select(Resume.resume_text).where(Resume.id == resume_id))
            return str(value) if value is not None else None

    async def core_session_public_id(self, session_id: int) -> str | None:
        async with self._sessions() as session:
            value = await session.scalar(
                select(InterviewSession.session_id)
                .join(
                    VoiceInterviewSession,
                    VoiceInterviewSession.interview_session_id == InterviewSession.id,
                )
                .where(VoiceInterviewSession.id == session_id)
            )
            return str(value) if value is not None else None

    async def find_by_core_public_id(
        self,
        core_session_id: str,
    ) -> VoiceInterviewSession | None:
        async with self._sessions() as session:
            return cast(
                VoiceInterviewSession | None,
                await session.scalar(
                    select(VoiceInterviewSession)
                    .join(
                        InterviewSession,
                        InterviewSession.id == VoiceInterviewSession.interview_session_id,
                    )
                    .where(InterviewSession.session_id == core_session_id)
                ),
            )

    async def core_evaluate_status(self, session_id: int) -> str | None:
        async with self._sessions() as session:
            return await session.scalar(
                select(InterviewSession.evaluate_status)
                .join(
                    VoiceInterviewSession,
                    VoiceInterviewSession.interview_session_id == InterviewSession.id,
                )
                .where(VoiceInterviewSession.id == session_id)
            )

    async def list_sessions(
        self,
        user_id: str,
        status: str | None,
    ) -> list[VoiceSessionListRow]:
        async with self._sessions() as session:
            statement = (
                select(
                    VoiceInterviewSession,
                    func.count(VoiceInterviewMessage.id),
                    InterviewSession.evaluate_status,
                    InterviewSession.evaluate_error,
                    InterviewSession.overall_score,
                )
                .join(
                    InterviewSession,
                    InterviewSession.id == VoiceInterviewSession.interview_session_id,
                )
                .outerjoin(
                    VoiceInterviewMessage,
                    and_(
                        VoiceInterviewMessage.session_id == VoiceInterviewSession.id,
                        VoiceInterviewMessage.message_type != SUMMARY_MESSAGE_TYPE,
                    ),
                )
                .where(VoiceInterviewSession.user_id == user_id)
                .group_by(
                    VoiceInterviewSession.id,
                    InterviewSession.evaluate_status,
                    InterviewSession.evaluate_error,
                    InterviewSession.overall_score,
                )
                .order_by(VoiceInterviewSession.updated_at.desc())
            )
            if status is not None:
                statement = statement.where(VoiceInterviewSession.status == status)
            rows = (await session.execute(statement)).all()
            return [
                VoiceSessionListRow(
                    session=row[0],
                    message_count=int(row[1]),
                    evaluate_status=row[2],
                    evaluate_error=row[3],
                    overall_score=row[4],
                )
                for row in rows
            ]

    async def update_phase(self, session_id: int, phase: str) -> VoiceInterviewSession | None:
        async with self._sessions() as session, session.begin():
            entity = await session.get(VoiceInterviewSession, session_id)
            if entity is None:
                return None
            entity.current_phase = phase
            entity.updated_at = self._now()
            return entity

    async def end_session(
        self,
        session_id: int,
        *,
        only_if_in_progress: bool,
    ) -> VoiceInterviewSession | None:
        async with self._sessions() as session, session.begin():
            entity = await session.get(VoiceInterviewSession, session_id)
            if entity is None:
                return None
            if only_if_in_progress and entity.status != "IN_PROGRESS":
                return None
            timestamp = self._now()
            entity.end_time = timestamp
            entity.current_phase = "COMPLETED"
            entity.status = "COMPLETED"
            entity.actual_duration = int(
                (timestamp - (entity.start_time or timestamp)).total_seconds()
            )
            entity.evaluate_status = "PENDING"
            entity.evaluate_error = None
            entity.updated_at = timestamp
            return entity

    async def pause_session(self, session_id: int) -> VoiceInterviewSession | None:
        async with self._sessions() as session, session.begin():
            entity = await session.get(VoiceInterviewSession, session_id)
            if entity is None:
                return None
            timestamp = self._now()
            entity.status = "PAUSED"
            entity.paused_at = timestamp
            entity.updated_at = timestamp
            return entity

    async def resume_session(self, session_id: int) -> VoiceInterviewSession | None:
        async with self._sessions() as session, session.begin():
            entity = await session.get(VoiceInterviewSession, session_id)
            if entity is None:
                return None
            timestamp = self._now()
            entity.status = "IN_PROGRESS"
            entity.resumed_at = timestamp
            entity.updated_at = timestamp
            return entity

    async def messages(self, session_id: int) -> list[VoiceInterviewMessage]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(VoiceInterviewMessage)
                .where(
                    VoiceInterviewMessage.session_id == session_id,
                    VoiceInterviewMessage.message_type != SUMMARY_MESSAGE_TYPE,
                )
                .order_by(VoiceInterviewMessage.sequence_num.asc())
            )
            return list(result)

    async def dialogue_count(self, session_id: int) -> int:
        async with self._sessions() as session:
            value = await session.scalar(
                select(func.count(VoiceInterviewMessage.id)).where(
                    VoiceInterviewMessage.session_id == session_id,
                    VoiceInterviewMessage.message_type != SUMMARY_MESSAGE_TYPE,
                )
            )
            return int(value or 0)

    async def save_message(
        self,
        session_id: int,
        user_text: str | None,
        ai_text: str | None,
        interview_turn_id: UUID | None = None,
    ) -> VoiceInterviewMessage | None:
        normalized_user = trim_to_none(user_text)
        normalized_ai = trim_to_none(ai_text)
        async with self._sessions() as session, session.begin():
            if interview_turn_id is not None:
                existing = await session.scalar(
                    select(VoiceInterviewMessage).where(
                        VoiceInterviewMessage.interview_turn_id == interview_turn_id
                    )
                )
                if existing is not None:
                    return existing
            voice_session = await session.get(VoiceInterviewSession, session_id)
            if voice_session is None:
                return None
            answer_attached = False
            if normalized_user is not None:
                unanswered = await session.scalar(
                    select(VoiceInterviewMessage)
                    .where(
                        VoiceInterviewMessage.session_id == session_id,
                        VoiceInterviewMessage.user_recognized_text.is_(None),
                        VoiceInterviewMessage.ai_generated_text.is_not(None),
                        VoiceInterviewMessage.message_type != SUMMARY_MESSAGE_TYPE,
                    )
                    .order_by(VoiceInterviewMessage.sequence_num.desc())
                    .limit(1)
                )
                if unanswered is not None:
                    unanswered.user_recognized_text = normalized_user
                    unanswered.interview_turn_id = interview_turn_id
                    answer_attached = True
            if normalized_ai is None:
                return None
            count = await session.scalar(
                select(func.count(VoiceInterviewMessage.id)).where(
                    VoiceInterviewMessage.session_id == session_id,
                    VoiceInterviewMessage.message_type != SUMMARY_MESSAGE_TYPE,
                )
            )
            timestamp = self._now()
            message = VoiceInterviewMessage(
                ai_generated_text=normalized_ai,
                created_at=timestamp,
                interview_turn_id=(interview_turn_id if not answer_attached else None),
                message_type=DIALOGUE_MESSAGE_TYPE,
                phase=voice_session.current_phase,
                sequence_num=int(count or 0) + 1,
                session_id=session_id,
                timestamp=timestamp,
                user_recognized_text=(
                    normalized_user if normalized_user is not None and not answer_attached else None
                ),
            )
            session.add(message)
            await session.flush()
            return message

    async def delete_session(self, session_id: int) -> bool:
        async with self._sessions() as session, session.begin():
            entity = await session.get(VoiceInterviewSession, session_id)
            if entity is None:
                return False
            await session.execute(
                delete(VoiceInterviewMessage).where(VoiceInterviewMessage.session_id == session_id)
            )
            await session.delete(entity)
            return True

    async def update_evaluate_status(
        self,
        session_id: int,
        status: str,
        error: str | None,
    ) -> bool:
        async with self._sessions() as session, session.begin():
            entity = await session.get(VoiceInterviewSession, session_id)
            if entity is None:
                return False
            entity.evaluate_status = status
            entity.evaluate_error = error
            entity.updated_at = self._now()
            return True

    async def stale_in_progress(self, before: datetime) -> list[VoiceInterviewSession]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(VoiceInterviewSession).where(
                    VoiceInterviewSession.status == "IN_PROGRESS",
                    VoiceInterviewSession.start_time < before,
                )
            )
            return list(result)
