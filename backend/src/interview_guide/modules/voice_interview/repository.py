from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.db.models import (
    Resume,
    VoiceInterviewEvaluation,
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
    ) -> VoiceInterviewSession:
        timestamp = self._now()
        async with self._sessions() as session, session.begin():
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
                )
                .outerjoin(
                    VoiceInterviewMessage,
                    and_(
                        VoiceInterviewMessage.session_id == VoiceInterviewSession.id,
                        VoiceInterviewMessage.message_type != SUMMARY_MESSAGE_TYPE,
                    ),
                )
                .where(VoiceInterviewSession.user_id == user_id)
                .group_by(VoiceInterviewSession.id)
                .order_by(VoiceInterviewSession.updated_at.desc())
            )
            if status is not None:
                statement = statement.where(VoiceInterviewSession.status == status)
            rows = (await session.execute(statement)).all()
            return [VoiceSessionListRow(session=row[0], message_count=int(row[1])) for row in rows]

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
    ) -> VoiceInterviewMessage | None:
        normalized_user = trim_to_none(user_text)
        normalized_ai = trim_to_none(ai_text)
        async with self._sessions() as session, session.begin():
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

    async def summary_row(self, session_id: int) -> VoiceInterviewMessage | None:
        async with self._sessions() as session:
            result = await session.scalars(
                select(VoiceInterviewMessage)
                .where(
                    VoiceInterviewMessage.session_id == session_id,
                    VoiceInterviewMessage.message_type == SUMMARY_MESSAGE_TYPE,
                )
                .order_by(VoiceInterviewMessage.sequence_num.asc())
                .limit(1)
            )
            return result.first()

    async def save_summary(
        self,
        session_id: int,
        summary: str,
        covered_turns: int,
    ) -> None:
        async with self._sessions() as session, session.begin():
            voice_session = await session.scalar(
                select(VoiceInterviewSession)
                .where(VoiceInterviewSession.id == session_id)
                .with_for_update()
            )
            if voice_session is None:
                raise LookupError(f"会话不存在: {session_id}")
            row = await session.scalar(
                select(VoiceInterviewMessage)
                .where(
                    VoiceInterviewMessage.session_id == session_id,
                    VoiceInterviewMessage.message_type == SUMMARY_MESSAGE_TYPE,
                )
                .order_by(VoiceInterviewMessage.sequence_num.asc())
                .limit(1)
            )
            timestamp = self._now()
            if row is None:
                row = VoiceInterviewMessage(
                    ai_generated_text=summary,
                    created_at=timestamp,
                    message_type=SUMMARY_MESSAGE_TYPE,
                    phase=None,
                    sequence_num=-(covered_turns + 1),
                    session_id=session_id,
                    timestamp=timestamp,
                    user_recognized_text=None,
                )
                session.add(row)
            else:
                row.ai_generated_text = summary
                row.sequence_num = -(covered_turns + 1)

    async def delete_session(self, session_id: int) -> bool:
        async with self._sessions() as session, session.begin():
            entity = await session.get(VoiceInterviewSession, session_id)
            if entity is None:
                return False
            await session.execute(
                delete(VoiceInterviewEvaluation).where(
                    VoiceInterviewEvaluation.session_id == session_id
                )
            )
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

    async def evaluation(self, session_id: int) -> VoiceInterviewEvaluation | None:
        async with self._sessions() as session:
            result = await session.scalars(
                select(VoiceInterviewEvaluation).where(
                    VoiceInterviewEvaluation.session_id == session_id
                )
            )
            return result.first()

    async def save_evaluation(self, entity: VoiceInterviewEvaluation) -> None:
        async with self._sessions() as session, session.begin():
            session.add(entity)

    async def save_empty_evaluation(
        self,
        session_id: int,
        role_type: str,
        interview_date: datetime | None,
    ) -> None:
        async with self._sessions() as session, session.begin():
            entity = await session.scalar(
                select(VoiceInterviewEvaluation).where(
                    VoiceInterviewEvaluation.session_id == session_id
                )
            )
            if entity is None:
                entity = VoiceInterviewEvaluation(
                    session_id=session_id,
                    created_at=self._now(),
                )
                session.add(entity)
            entity.overall_score = None
            entity.overall_feedback = "本次语音面试未形成有效对话记录，暂无可评估内容。"
            entity.question_evaluations_json = "[]"
            entity.strengths_json = "[]"
            entity.improvements_json = '["请先完成至少一轮有效问答后再生成评估。"]'
            entity.reference_answers_json = "[]"
            entity.interviewer_role = role_type
            entity.interview_date = interview_date

    async def stale_in_progress(self, before: datetime) -> list[VoiceInterviewSession]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(VoiceInterviewSession).where(
                    VoiceInterviewSession.status == "IN_PROGRESS",
                    VoiceInterviewSession.start_time < before,
                )
            )
            return list(result)

    async def stale_evaluations(
        self,
        status: str,
        before: datetime,
    ) -> list[VoiceInterviewSession]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(VoiceInterviewSession).where(
                    VoiceInterviewSession.evaluate_status == status,
                    VoiceInterviewSession.updated_at < before,
                )
            )
            return list(result)
