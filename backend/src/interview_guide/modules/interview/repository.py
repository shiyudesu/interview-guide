from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.api.models import compact_json_text
from interview_guide.common.db.models import InterviewAnswer, InterviewSession, Resume
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.modules.interview.models import (
    HistoricalQuestion,
    InterviewQuestion,
    InterviewReportDTO,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionRecord:
    session: InterviewSession
    resume_text: str


class InterviewRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime],
    ) -> None:
        self._sessions = sessions
        self._now = now

    async def list_sessions(self) -> list[InterviewSession]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(InterviewSession).order_by(InterviewSession.created_at.desc())
            )
            return list(result)

    async def find_session(self, session_id: str) -> SessionRecord | None:
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(InterviewSession, Resume.resume_text)
                    .outerjoin(Resume, Resume.id == InterviewSession.resume_id)
                    .where(InterviewSession.session_id == session_id)
                )
            ).first()
            if row is None:
                return None
            return SessionRecord(row[0], str(row[1] or ""))

    async def find_by_request_id(self, request_id: str) -> SessionRecord | None:
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(InterviewSession, Resume.resume_text)
                    .outerjoin(Resume, Resume.id == InterviewSession.resume_id)
                    .where(InterviewSession.request_id == request_id)
                )
            ).first()
            if row is None:
                return None
            return SessionRecord(row[0], str(row[1] or ""))

    async def find_unfinished(self, resume_id: int) -> SessionRecord | None:
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(InterviewSession, Resume.resume_text)
                    .outerjoin(Resume, Resume.id == InterviewSession.resume_id)
                    .where(
                        InterviewSession.resume_id == resume_id,
                        InterviewSession.status.in_(("CREATED", "IN_PROGRESS")),
                    )
                    .order_by(InterviewSession.created_at.desc())
                    .limit(1)
                )
            ).first()
            if row is None:
                return None
            return SessionRecord(row[0], str(row[1] or ""))

    async def create_session(
        self,
        *,
        session_id: str,
        resume_id: int | None,
        questions: list[InterviewQuestion],
        llm_provider: str | None,
        skill_id: str | None,
        difficulty: str | None,
        request_id: str | None,
        source_type: str = "NORMAL",
        knowledge_base_id: int | None = None,
        interview_category: str | None = None,
    ) -> InterviewSession:
        async with self._sessions() as session, session.begin():
            linked_resume_id: int | None = None
            if resume_id is not None:
                linked_resume_id = await session.scalar(
                    select(Resume.id).where(Resume.id == resume_id)
                )
            entity = InterviewSession(
                completed_at=None,
                created_at=self._now(),
                current_question_index=0,
                difficulty=difficulty or "mid",
                evaluate_error=None,
                evaluate_status=None,
                improvements_json=None,
                interview_category=interview_category,
                knowledge_base_id=knowledge_base_id,
                llm_provider=llm_provider if llm_provider is not None else "default",
                overall_feedback=None,
                overall_score=None,
                questions_json=compact_json_text(
                    [item.model_dump(by_alias=True) for item in questions]
                ),
                reference_answers_json=None,
                request_id=request_id,
                resume_id=linked_resume_id,
                session_id=session_id,
                skill_id=skill_id or "java-backend",
                source_type=source_type or "NORMAL",
                status="CREATED",
                strengths_json=None,
                total_questions=len(questions),
            )
            session.add(entity)
            await session.flush()
            return entity

    async def update_session_status(self, session_id: str, status: str) -> None:
        async with self._sessions() as session, session.begin():
            entity = await self._session_entity(session, session_id)
            if entity is None:
                return
            entity.status = status
            if status in {"COMPLETED", "EVALUATED"}:
                entity.completed_at = self._now()

    async def update_evaluate_status(
        self,
        session_id: str,
        status: str,
        error: str | None,
    ) -> bool:
        async with self._sessions() as session, session.begin():
            entity = await self._session_entity(session, session_id)
            if entity is None:
                return False
            entity.evaluate_status = status
            entity.evaluate_error = error[:500] if error is not None else None
            return True

    async def update_current_question_index(self, session_id: str, index: int) -> None:
        async with self._sessions() as session, session.begin():
            entity = await self._session_entity(session, session_id)
            if entity is None:
                return
            entity.current_question_index = index
            entity.status = "IN_PROGRESS"

    async def save_answer(
        self,
        session_id: str,
        question_index: int,
        question: str,
        category: str | None,
        user_answer: str | None,
        score: int,
        feedback: str | None,
    ) -> None:
        async with self._sessions() as session, session.begin():
            entity = await self._session_entity(session, session_id)
            if entity is None:
                raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)
            statement = insert(InterviewAnswer).values(
                answered_at=self._now(),
                category=category,
                feedback=feedback,
                key_points_json=None,
                question=question,
                question_index=question_index,
                reference_answer=None,
                score=score,
                user_answer=user_answer,
                session_id=entity.id,
            )
            await session.execute(
                statement.on_conflict_do_update(
                    constraint="uk_interview_answer_session_question",
                    set_={
                        "category": statement.excluded.category,
                        "feedback": statement.excluded.feedback,
                        "question": statement.excluded.question,
                        "score": statement.excluded.score,
                        "user_answer": statement.excluded.user_answer,
                    },
                )
            )

    async def answers(self, session_id: str) -> list[InterviewAnswer]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(InterviewAnswer)
                .join(
                    InterviewSession,
                    InterviewSession.id == InterviewAnswer.session_id,
                )
                .where(InterviewSession.session_id == session_id)
                .order_by(InterviewAnswer.question_index)
            )
            return list(result)

    async def save_report(
        self,
        session_id: str,
        report: InterviewReportDTO,
    ) -> None:
        strengths_json = compact_json_text(report.strengths)
        improvements_json = compact_json_text(report.improvements)
        references_json = compact_json_text(
            [item.model_dump(by_alias=True) for item in report.reference_answers]
        )
        reference_by_index = {item.question_index: item for item in report.reference_answers}
        async with self._sessions() as session, session.begin():
            entity = await self._session_entity(session, session_id)
            if entity is None:
                return
            entity.overall_score = report.overall_score
            entity.overall_feedback = report.overall_feedback
            entity.strengths_json = strengths_json
            entity.improvements_json = improvements_json
            entity.reference_answers_json = references_json
            entity.status = "EVALUATED"
            entity.completed_at = self._now()
            existing = list(
                await session.scalars(
                    select(InterviewAnswer).where(InterviewAnswer.session_id == entity.id)
                )
            )
            answer_by_index = {cast(int, answer.question_index): answer for answer in existing}
            for evaluation in report.question_details:
                answer = answer_by_index.get(evaluation.question_index)
                if answer is None:
                    answer = InterviewAnswer(
                        answered_at=self._now(),
                        category=evaluation.category,
                        question=evaluation.question,
                        question_index=evaluation.question_index,
                        session_id=entity.id,
                        user_answer=None,
                    )
                    session.add(answer)
                answer.score = evaluation.score
                answer.feedback = evaluation.feedback
                reference = reference_by_index.get(evaluation.question_index)
                if reference is not None:
                    answer.reference_answer = reference.reference_answer
                    if reference.key_points:
                        answer.key_points_json = compact_json_text(reference.key_points)

    async def delete_session(self, session_id: str) -> None:
        async with self._sessions() as session, session.begin():
            entity = await self._session_entity(session, session_id)
            if entity is None:
                raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)
            await session.execute(
                delete(InterviewAnswer).where(InterviewAnswer.session_id == entity.id)
            )
            await session.delete(entity)

    async def historical_questions(
        self,
        skill_id: str,
        resume_id: int | None,
    ) -> list[HistoricalQuestion]:
        async with self._sessions() as session:
            statement = select(InterviewSession.questions_json).where(
                InterviewSession.skill_id == skill_id
            )
            if resume_id is not None:
                statement = statement.where(InterviewSession.resume_id == resume_id)
            result = await session.scalars(
                statement.order_by(InterviewSession.created_at.desc()).limit(10)
            )
            seen: set[str] = set()
            historical: list[HistoricalQuestion] = []
            for raw in result:
                if not raw:
                    continue
                try:
                    questions = [InterviewQuestion.model_validate(item) for item in json.loads(raw)]
                except Exception:
                    logger.exception("failed to parse historical interview questions")
                    continue
                for question in questions:
                    if question.is_follow_up or question.question in seen:
                        continue
                    seen.add(question.question)
                    historical.append(
                        HistoricalQuestion(
                            question=question.question,
                            type=question.type,
                            topic_summary=question.topic_summary,
                        )
                    )
                    if len(historical) == 60:
                        return historical
            return historical

    async def _session_entity(
        self,
        session: AsyncSession,
        session_id: str,
    ) -> InterviewSession | None:
        return cast(
            InterviewSession | None,
            await session.scalar(
                select(InterviewSession).where(InterviewSession.session_id == session_id)
            ),
        )
