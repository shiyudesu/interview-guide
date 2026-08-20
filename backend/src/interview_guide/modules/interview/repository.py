from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.api.models import compact_json_text
from interview_guide.common.db.models import (
    InterviewQuestionRecord,
    InterviewSession,
    InterviewTurnRecord,
    Resume,
)
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.modules.interview.models import (
    InterviewChannel,
    InterviewReportDTO,
    PlannedInterviewQuestion,
    QuestionKind,
    TurnAction,
    TurnDecisionStatus,
)


@dataclass(frozen=True)
class SessionAggregate:
    session: InterviewSession
    resume_text: str
    questions: list[InterviewQuestionRecord]
    turns: list[InterviewTurnRecord]


@dataclass(frozen=True)
class TurnStart:
    aggregate: SessionAggregate
    turn: InterviewTurnRecord
    existing: bool


@dataclass(frozen=True)
class FinalizeTurn:
    aggregate: SessionAggregate
    turn: InterviewTurnRecord
    evaluation_pending: bool


class InterviewRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime],
        *,
        uuid_factory: Callable[[], UUID] = uuid.uuid4,
    ) -> None:
        self._sessions = sessions
        self._now = now
        self._uuid_factory = uuid_factory

    async def list_sessions(
        self,
        *,
        session_ids: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[tuple[InterviewSession, int]]:
        async with self._sessions() as session:
            answered_main = (
                select(
                    InterviewTurnRecord.interview_session_id.label("session_id"),
                    func.count(InterviewTurnRecord.id).label("answered_main"),
                )
                .join(
                    InterviewQuestionRecord,
                    InterviewQuestionRecord.id == InterviewTurnRecord.question_id,
                )
                .where(InterviewQuestionRecord.kind == QuestionKind.MAIN.value)
                .group_by(InterviewTurnRecord.interview_session_id)
                .subquery()
            )
            statement = (
                select(
                    InterviewSession,
                    func.coalesce(answered_main.c.answered_main, 0),
                )
                .outerjoin(answered_main, answered_main.c.session_id == InterviewSession.id)
                .order_by(InterviewSession.created_at.desc())
            )
            if session_ids is not None:
                statement = statement.where(InterviewSession.session_id.in_(session_ids))
            if offset:
                statement = statement.offset(offset)
            if limit is not None:
                statement = statement.limit(limit)
            rows = await session.execute(statement)
            return [(row[0], int(row[1])) for row in rows]

    async def find_session(self, session_id: str) -> SessionAggregate | None:
        async with self._sessions() as session:
            return await self._aggregate(session, session_id)

    async def find_by_request_id(self, request_id: str) -> SessionAggregate | None:
        async with self._sessions() as session:
            public_id = await session.scalar(
                select(InterviewSession.session_id).where(InterviewSession.request_id == request_id)
            )
            return await self._aggregate(session, public_id) if public_id is not None else None

    async def find_unfinished(
        self,
        resume_id: int,
        channel: InterviewChannel = InterviewChannel.TEXT,
    ) -> SessionAggregate | None:
        async with self._sessions() as session:
            public_id = await session.scalar(
                select(InterviewSession.session_id)
                .where(
                    InterviewSession.resume_id == resume_id,
                    InterviewSession.channel == channel.value,
                    InterviewSession.status.in_(("CREATED", "IN_PROGRESS")),
                )
                .order_by(InterviewSession.created_at.desc())
                .limit(1)
            )
            return await self._aggregate(session, public_id) if public_id is not None else None

    async def resume_text(self, resume_id: int | None) -> str:
        if resume_id is None:
            return ""
        async with self._sessions() as session:
            value = await session.scalar(select(Resume.resume_text).where(Resume.id == resume_id))
            return str(value or "")

    async def create_session(
        self,
        *,
        session_id: str,
        channel: InterviewChannel,
        resume_id: int | None,
        questions: Sequence[PlannedInterviewQuestion],
        max_follow_ups_per_main: int,
        llm_provider: str | None,
        skill_id: str | None,
        difficulty: str | None,
        request_id: str | None,
        knowledge_base_id: int | None = None,
        interview_category: str | None = None,
        context_json: str | None = None,
    ) -> SessionAggregate:
        if not questions:
            raise BusinessException(
                ErrorCode.INTERVIEW_QUESTION_NOT_FOUND,
                "面试题目不能为空",
            )
        async with self._sessions() as session, session.begin():
            linked_resume_id: int | None = None
            resume_text = ""
            if resume_id is not None:
                row = (
                    await session.execute(
                        select(Resume.id, Resume.resume_text).where(Resume.id == resume_id)
                    )
                ).first()
                if row is not None:
                    linked_resume_id = int(row[0])
                    resume_text = str(row[1] or "")
            entity = InterviewSession(
                channel=channel.value,
                completed_at=None,
                context_json=context_json,
                created_at=self._now(),
                current_question_id=None,
                difficulty=difficulty or "mid",
                evaluate_error=None,
                evaluate_status=None,
                improvements_json=None,
                interview_category=interview_category,
                knowledge_base_id=knowledge_base_id,
                llm_provider=llm_provider if llm_provider is not None else "default",
                max_follow_ups_per_main=max_follow_ups_per_main,
                overall_feedback=None,
                overall_score=None,
                planned_main_question_count=len(questions),
                reference_answers_json=None,
                request_id=request_id,
                resume_id=linked_resume_id,
                session_id=session_id,
                skill_id=skill_id or "java-backend",
                status="CREATED",
                strengths_json=None,
            )
            session.add(entity)
            await session.flush()
            records = [
                self._new_main_question(entity.id, index, question)
                for index, question in enumerate(questions)
            ]
            session.add_all(records)
            await session.flush()
            entity.current_question_id = records[0].id
        return SessionAggregate(entity, resume_text, records, [])

    async def begin_turn(
        self,
        session_id: str,
        question_id: UUID,
        request_id: str,
        answer: str | None,
        answer_hash: str,
        lease_expires_at: datetime,
    ) -> TurnStart:
        async with self._sessions() as session, session.begin():
            entity = cast(
                InterviewSession | None,
                await session.scalar(
                    select(InterviewSession)
                    .where(InterviewSession.session_id == session_id)
                    .with_for_update()
                ),
            )
            if entity is None:
                raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)
            aggregate = await self._aggregate_for_entity(session, entity)
            existing = await session.scalar(
                select(InterviewTurnRecord).where(
                    InterviewTurnRecord.interview_session_id == entity.id,
                    InterviewTurnRecord.request_id == request_id,
                )
            )
            if existing is not None:
                return TurnStart(aggregate, existing, True)
            answered = await session.scalar(
                select(InterviewTurnRecord).where(
                    InterviewTurnRecord.interview_session_id == entity.id,
                    InterviewTurnRecord.question_id == question_id,
                )
            )
            if answered is not None:
                return TurnStart(aggregate, answered, True)
            if entity.status in {"COMPLETED", "EVALUATED"}:
                raise BusinessException(ErrorCode.INTERVIEW_ALREADY_COMPLETED)
            if entity.current_question_id != question_id:
                raise BusinessException(
                    ErrorCode.INTERVIEW_QUESTION_NOT_FOUND,
                    "提交的问题不是当前问题",
                )
            turn = InterviewTurnRecord(
                id=self._uuid_factory(),
                acknowledgement=None,
                action=None,
                answer=answer,
                answer_hash=answer_hash,
                answered_at=self._now(),
                completion_tokens=None,
                confidence=None,
                decided_at=None,
                decision_duration_ms=None,
                decision_reason=None,
                decision_status=TurnDecisionStatus.PROCESSING.value,
                error=None,
                interview_session_id=entity.id,
                lease_expires_at=lease_expires_at,
                model_name=None,
                next_question_id=None,
                processing_started_at=self._now(),
                prompt_tokens=None,
                prompt_version=None,
                provider_id=None,
                question_id=question_id,
                reason_code=None,
                request_id=request_id,
                schema_version=None,
                target_topic=None,
                total_tokens=None,
            )
            session.add(turn)
            if entity.status == "CREATED":
                entity.status = "IN_PROGRESS"
            await session.flush()
            aggregate.turns.append(turn)
            return TurnStart(aggregate, turn, False)

    async def turn(self, session_id: str, turn_id: UUID) -> InterviewTurnRecord | None:
        async with self._sessions() as session:
            return cast(
                InterviewTurnRecord | None,
                await session.scalar(
                    select(InterviewTurnRecord)
                    .join(
                        InterviewSession,
                        InterviewSession.id == InterviewTurnRecord.interview_session_id,
                    )
                    .where(
                        InterviewSession.session_id == session_id,
                        InterviewTurnRecord.id == turn_id,
                    )
                ),
            )

    async def finalize_turn(
        self,
        session_id: str,
        turn_id: UUID,
        *,
        action: TurnAction,
        acknowledgement: str,
        follow_up_question: str | None,
        decision_reason: str,
        reason_code: str,
        target_topic: str | None,
        confidence: float | None,
        decision_status: TurnDecisionStatus,
        provider_id: str | None,
        model_name: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        total_tokens: int | None,
        duration_ms: int,
        error: str | None,
    ) -> FinalizeTurn:
        evaluation_pending = False
        async with self._sessions() as session, session.begin():
            entity = cast(
                InterviewSession | None,
                await session.scalar(
                    select(InterviewSession)
                    .where(InterviewSession.session_id == session_id)
                    .with_for_update()
                ),
            )
            if entity is None:
                raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)
            turn = cast(
                InterviewTurnRecord | None,
                await session.scalar(
                    select(InterviewTurnRecord)
                    .where(
                        InterviewTurnRecord.id == turn_id,
                        InterviewTurnRecord.interview_session_id == entity.id,
                    )
                    .with_for_update()
                ),
            )
            if turn is None:
                raise BusinessException(ErrorCode.INTERVIEW_QUESTION_NOT_FOUND)
            if turn.decision_status != TurnDecisionStatus.PROCESSING.value:
                aggregate = await self._aggregate_for_entity(session, entity)
                return FinalizeTurn(aggregate, turn, False)
            if entity.current_question_id != turn.question_id:
                raise BusinessException(
                    ErrorCode.BAD_REQUEST,
                    "面试轮次状态已变化，请刷新后重试",
                )
            current = cast(
                InterviewQuestionRecord,
                await session.scalar(
                    select(InterviewQuestionRecord).where(
                        InterviewQuestionRecord.id == turn.question_id
                    )
                ),
            )
            next_question: InterviewQuestionRecord | None = None
            effective_action = action
            if action == TurnAction.FOLLOW_UP and follow_up_question is not None:
                parent_id = (
                    current.id
                    if current.kind == QuestionKind.MAIN.value
                    else cast(UUID, current.parent_question_id)
                )
                follow_up_count = int(
                    await session.scalar(
                        select(func.count(InterviewQuestionRecord.id)).where(
                            InterviewQuestionRecord.interview_session_id == entity.id,
                            InterviewQuestionRecord.main_order == current.main_order,
                            InterviewQuestionRecord.kind == QuestionKind.FOLLOW_UP.value,
                        )
                    )
                    or 0
                )
                if follow_up_count < entity.max_follow_ups_per_main:
                    next_question = InterviewQuestionRecord(
                        id=self._uuid_factory(),
                        category=current.category,
                        created_at=self._now(),
                        follow_up_order=follow_up_count + 1,
                        interview_session_id=entity.id,
                        key_points_json=current.key_points_json,
                        kind=QuestionKind.FOLLOW_UP.value,
                        main_order=current.main_order,
                        parent_question_id=parent_id,
                        phase=current.phase,
                        question=follow_up_question,
                        reference_answer=None,
                        scoring_rubric=current.scoring_rubric,
                        source_context=current.source_context,
                        source_question_id=current.source_question_id,
                        topic_summary=target_topic or current.topic_summary,
                        type=current.type,
                    )
                    session.add(next_question)
                    await session.flush()
                else:
                    effective_action = TurnAction.NEXT_MAIN
            if effective_action == TurnAction.NEXT_MAIN:
                next_question = cast(
                    InterviewQuestionRecord | None,
                    await session.scalar(
                        select(InterviewQuestionRecord)
                        .where(
                            InterviewQuestionRecord.interview_session_id == entity.id,
                            InterviewQuestionRecord.kind == QuestionKind.MAIN.value,
                            InterviewQuestionRecord.main_order > current.main_order,
                        )
                        .order_by(InterviewQuestionRecord.main_order)
                        .limit(1)
                    ),
                )
                if next_question is None:
                    effective_action = TurnAction.COMPLETE
            if effective_action == TurnAction.COMPLETE:
                entity.current_question_id = None
                entity.status = "COMPLETED"
                entity.completed_at = self._now()
                entity.evaluate_status = "PENDING"
                entity.evaluate_error = None
                evaluation_pending = True
                next_question = None
            else:
                assert next_question is not None
                entity.current_question_id = next_question.id
                entity.status = "IN_PROGRESS"
            turn.action = effective_action.value
            turn.acknowledgement = acknowledgement[:200]
            turn.next_question_id = next_question.id if next_question is not None else None
            turn.decision_reason = decision_reason[:500]
            turn.reason_code = reason_code[:64]
            turn.target_topic = target_topic[:128] if target_topic is not None else None
            turn.confidence = confidence
            turn.decision_status = decision_status.value
            turn.provider_id = provider_id
            turn.model_name = model_name
            turn.prompt_version = "v1"
            turn.schema_version = "v1"
            turn.prompt_tokens = prompt_tokens
            turn.completion_tokens = completion_tokens
            turn.total_tokens = total_tokens
            turn.decision_duration_ms = duration_ms
            turn.error = error[:500] if error is not None else None
            turn.decided_at = self._now()
            await session.flush()
            aggregate = await self._aggregate_for_entity(session, entity)
            return FinalizeTurn(aggregate, turn, evaluation_pending)

    async def complete_session(self, session_id: str) -> bool:
        async with self._sessions() as session, session.begin():
            entity = cast(
                InterviewSession | None,
                await session.scalar(
                    select(InterviewSession)
                    .where(InterviewSession.session_id == session_id)
                    .with_for_update()
                ),
            )
            if entity is None:
                raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)
            if entity.status in {"COMPLETED", "EVALUATED"}:
                return False
            entity.status = "COMPLETED"
            entity.current_question_id = None
            entity.completed_at = self._now()
            entity.evaluate_status = "PENDING"
            entity.evaluate_error = None
            return True

    async def update_evaluate_status(
        self,
        session_id: str,
        status: str,
        error: str | None,
    ) -> bool:
        async with self._sessions() as session, session.begin():
            entity = await session.scalar(
                select(InterviewSession).where(InterviewSession.session_id == session_id)
            )
            if entity is None:
                return False
            entity.evaluate_status = status
            entity.evaluate_error = error[:500] if error is not None else None
            return True

    async def pending_evaluations(self, before: datetime) -> list[str]:
        async with self._sessions() as session:
            values = await session.scalars(
                select(InterviewSession.session_id).where(
                    InterviewSession.evaluate_status == "PENDING",
                    InterviewSession.completed_at <= before,
                )
            )
            return list(values)

    async def stale_processing_turns(self, before: datetime) -> list[tuple[str, UUID]]:
        async with self._sessions() as session:
            rows = await session.execute(
                select(InterviewSession.session_id, InterviewTurnRecord.id)
                .join(
                    InterviewTurnRecord,
                    InterviewTurnRecord.interview_session_id == InterviewSession.id,
                )
                .where(
                    InterviewTurnRecord.decision_status == TurnDecisionStatus.PROCESSING.value,
                    InterviewTurnRecord.lease_expires_at <= before,
                )
            )
            return [(str(row[0]), cast(UUID, row[1])) for row in rows]

    async def save_report(self, session_id: str, report: InterviewReportDTO) -> None:
        async with self._sessions() as session, session.begin():
            entity = await session.scalar(
                select(InterviewSession).where(InterviewSession.session_id == session_id)
            )
            if entity is None:
                raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)
            entity.overall_score = report.overall_score
            entity.overall_feedback = report.overall_feedback
            entity.strengths_json = compact_json_text(report.strengths)
            entity.improvements_json = compact_json_text(report.improvements)
            entity.reference_answers_json = compact_json_text(
                report.model_dump(mode="json", by_alias=True)
            )
            entity.status = "EVALUATED"
            entity.evaluate_status = "COMPLETED"
            entity.evaluate_error = None
            entity.completed_at = entity.completed_at or self._now()

    async def saved_report(self, session_id: str) -> InterviewReportDTO | None:
        async with self._sessions() as session:
            raw = await session.scalar(
                select(InterviewSession.reference_answers_json).where(
                    InterviewSession.session_id == session_id
                )
            )
            if raw is None:
                return None
            return InterviewReportDTO.model_validate_json(raw)

    async def delete_session(self, session_id: str) -> None:
        async with self._sessions() as session, session.begin():
            entity = await session.scalar(
                select(InterviewSession).where(InterviewSession.session_id == session_id)
            )
            if entity is None:
                raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)
            entity.current_question_id = None
            await session.flush()
            await session.execute(
                delete(InterviewTurnRecord).where(
                    InterviewTurnRecord.interview_session_id == entity.id
                )
            )
            await session.execute(
                delete(InterviewQuestionRecord).where(
                    InterviewQuestionRecord.interview_session_id == entity.id
                )
            )
            await session.delete(entity)

    async def historical_questions(
        self,
        skill_id: str,
        resume_id: int | None,
    ) -> list[tuple[str, str | None, str | None]]:
        async with self._sessions() as session:
            statement = (
                select(
                    InterviewQuestionRecord.question,
                    InterviewQuestionRecord.type,
                    InterviewQuestionRecord.topic_summary,
                )
                .join(
                    InterviewSession,
                    InterviewSession.id == InterviewQuestionRecord.interview_session_id,
                )
                .where(
                    InterviewSession.skill_id == skill_id,
                    InterviewQuestionRecord.kind == QuestionKind.MAIN.value,
                )
            )
            if resume_id is not None:
                statement = statement.where(InterviewSession.resume_id == resume_id)
            rows = await session.execute(
                statement.order_by(InterviewSession.created_at.desc()).limit(60)
            )
            return [(str(row[0]), row[1], row[2]) for row in rows]

    async def _aggregate(
        self,
        session: AsyncSession,
        session_id: str | None,
    ) -> SessionAggregate | None:
        if session_id is None:
            return None
        row = (
            await session.execute(
                select(InterviewSession, Resume.resume_text)
                .outerjoin(Resume, Resume.id == InterviewSession.resume_id)
                .where(InterviewSession.session_id == session_id)
            )
        ).first()
        if row is None:
            return None
        return await self._aggregate_for_entity(session, row[0], str(row[1] or ""))

    async def _aggregate_for_entity(
        self,
        session: AsyncSession,
        entity: InterviewSession,
        resume_text: str | None = None,
    ) -> SessionAggregate:
        if resume_text is None and entity.resume_id is not None:
            resume_text = await session.scalar(
                select(Resume.resume_text).where(Resume.id == entity.resume_id)
            )
        questions = list(
            await session.scalars(
                select(InterviewQuestionRecord)
                .where(InterviewQuestionRecord.interview_session_id == entity.id)
                .order_by(
                    InterviewQuestionRecord.main_order,
                    InterviewQuestionRecord.follow_up_order,
                )
            )
        )
        turns = list(
            await session.scalars(
                select(InterviewTurnRecord)
                .where(InterviewTurnRecord.interview_session_id == entity.id)
                .order_by(InterviewTurnRecord.answered_at)
            )
        )
        return SessionAggregate(entity, str(resume_text or ""), questions, turns)

    def _new_main_question(
        self,
        session_id: int,
        order: int,
        question: PlannedInterviewQuestion,
    ) -> InterviewQuestionRecord:
        return InterviewQuestionRecord(
            id=self._uuid_factory(),
            category=question.category,
            created_at=self._now(),
            follow_up_order=0,
            interview_session_id=session_id,
            key_points_json=(
                compact_json_text(question.key_points) if question.key_points is not None else None
            ),
            kind=QuestionKind.MAIN.value,
            main_order=order,
            parent_question_id=None,
            phase=question.phase,
            question=question.question,
            reference_answer=question.reference_answer,
            scoring_rubric=question.scoring_rubric,
            source_context=question.source_context,
            source_question_id=question.source_question_id,
            topic_summary=question.topic_summary,
            type=question.type,
        )


def parse_key_points(value: str | None) -> list[str]:
    if value is None:
        return []
    document = json.loads(value)
    return [str(item) for item in document] if isinstance(document, list) else []
