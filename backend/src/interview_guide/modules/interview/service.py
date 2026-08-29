from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.opentrek import opentrek_provider_with_skills
from interview_guide.common.ai.providers import ProviderRegistry
from interview_guide.common.ai.user_providers import normalize_provider_alias
from interview_guide.common.api.models import compact_json_text
from interview_guide.common.db.models import InterviewQuestionRecord, InterviewTurnRecord
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.metrics import ApplicationMetrics
from interview_guide.common.redis.streams import (
    FIELD_RETRY_COUNT,
    FIELD_SESSION_ID,
    INTERVIEW_EVALUATE,
    RedisStreamService,
    StreamMessage,
)
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.infrastructure.export.pdf import PdfDocumentBuilder, pdf_download_headers
from interview_guide.modules.interview.cache import InterviewSessionCache
from interview_guide.modules.interview.evaluation import (
    UnifiedEvaluationService,
    parse_saved_list,
)
from interview_guide.modules.interview.models import (
    AnswerDetailDTO,
    CreateInterviewRequest,
    HistoricalQuestion,
    InterviewChannel,
    InterviewDetailDTO,
    InterviewProgressDTO,
    InterviewQuestionDTO,
    InterviewReportDTO,
    InterviewSessionDTO,
    InterviewSessionStatus,
    InterviewTurnDTO,
    PlannedInterviewQuestion,
    QuestionKind,
    SessionListItemDTO,
    SubmitTurnRequest,
    SubmitTurnResponse,
    TurnAction,
    TurnDecisionStatus,
)
from interview_guide.modules.interview.question import InterviewQuestionService
from interview_guide.modules.interview.repository import (
    FinalizeTurn,
    InterviewRepository,
    SessionAggregate,
)
from interview_guide.modules.interview.turn import (
    InterviewTurnDecisionService,
    TurnDecisionResult,
)

logger = logging.getLogger(__name__)


class InterviewService:
    def __init__(
        self,
        repository: InterviewRepository,
        cache: InterviewSessionCache,
        streams: RedisStreamService,
        questions: InterviewQuestionService,
        decisions: InterviewTurnDecisionService,
        registry: ProviderRegistry,
        blocking_executor: BlockingExecutor,
        *,
        follow_up_count: int,
        turn_lease_seconds: int,
        turn_wait_seconds: float,
        metrics: ApplicationMetrics | None = None,
        uuid_factory: Callable[[], UUID] = uuid.uuid4,
    ) -> None:
        self._repository = repository
        self._cache = cache
        self._streams = streams
        self._questions = questions
        self._decisions = decisions
        self._registry = registry
        self._blocking_executor = blocking_executor
        self._follow_up_count = follow_up_count
        self._turn_lease_seconds = turn_lease_seconds
        self._turn_wait_seconds = turn_wait_seconds
        self._uuid_factory = uuid_factory
        self._metrics = metrics

    @property
    def follow_up_count(self) -> int:
        return self._follow_up_count

    async def list_sessions(
        self,
        *,
        session_ids: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[SessionListItemDTO]:
        return [
            SessionListItemDTO(
                session_id=entity.session_id,
                channel=InterviewChannel(entity.channel),
                skill_id=entity.skill_id,
                difficulty=entity.difficulty,
                resume_id=entity.resume_id,
                planned_main_questions=entity.planned_main_question_count,
                answered_main_questions=answered_main,
                status=entity.status,
                evaluate_status=entity.evaluate_status,
                evaluate_error=entity.evaluate_error,
                overall_score=entity.overall_score,
                knowledge_base_id=entity.knowledge_base_id,
                interview_category=entity.interview_category,
                created_at=entity.created_at,
                completed_at=entity.completed_at,
            )
            for entity, answered_main in await self._repository.list_sessions(
                session_ids=session_ids,
                limit=limit,
                offset=offset,
            )
        ]

    async def create_session(self, request: CreateInterviewRequest) -> InterviewSessionDTO:
        if request.request_id is None:
            return await self._create_session_internal(request, None)

        async def operation() -> InterviewSessionDTO:
            return await self._create_idempotent(request, request.request_id or "")

        return await self._cache.execute_create_locked(request.request_id, operation)

    async def generate_main_questions(
        self,
        *,
        provider_id: str | None,
        skill_id: str,
        difficulty: str,
        resume_id: int | None,
        resume_text: str | None,
        question_count: int,
        jd_text: str | None,
    ) -> list[PlannedInterviewQuestion]:
        historical = [
            HistoricalQuestion(question=item[0], type=item[1], topic_summary=item[2])
            for item in await self._repository.historical_questions(skill_id, resume_id)
        ]
        effective_resume = (
            resume_text
            if resume_text is not None
            else await self._repository.resume_text(resume_id)
        )
        return await self._questions.generate(
            provider_id=provider_id,
            skill_id=skill_id,
            difficulty=difficulty,
            resume_text=effective_resume,
            question_count=question_count,
            historical_questions=historical,
            custom_categories=None,
            jd_text=jd_text,
        )

    async def create_session_from_questions(
        self,
        questions: list[PlannedInterviewQuestion],
        *,
        channel: InterviewChannel,
        max_follow_ups_per_main: int,
        llm_provider: str | None,
        skill_id: str,
        difficulty: str,
        request_id: str | None,
        resume_id: int | None = None,
        knowledge_base_id: int | None = None,
        interview_category: str | None = None,
        context: dict[str, object] | None = None,
    ) -> InterviewSessionDTO:
        if request_id is not None:
            existing = await self._repository.find_by_request_id(request_id)
            if existing is not None:
                return self._session_dto(existing)
        session_id = self._uuid_factory().hex[:16]
        resolved_provider = normalize_provider_alias(llm_provider)
        if resolved_provider is None:
            resolved_provider = await self._registry.default_chat_alias()
        try:
            aggregate = await self._repository.create_session(
                session_id=session_id,
                channel=channel,
                resume_id=resume_id,
                questions=questions,
                max_follow_ups_per_main=max_follow_ups_per_main,
                llm_provider=resolved_provider,
                skill_id=skill_id,
                difficulty=difficulty,
                request_id=request_id,
                knowledge_base_id=knowledge_base_id,
                interview_category=interview_category,
                context_json=compact_json_text(context) if context is not None else None,
            )
        except Exception:
            if request_id is not None:
                existing = await self._repository.find_by_request_id(request_id)
                if existing is not None:
                    return self._session_dto(existing)
            raise
        if request_id is not None:
            await self._cache.set_create_result(request_id, session_id)
        return self._session_dto(aggregate)

    async def get_session(self, session_id: str) -> InterviewSessionDTO:
        return self._session_dto(await self._required(session_id))

    async def find_unfinished_session(self, resume_id: int) -> InterviewSessionDTO | None:
        aggregate = await self._repository.find_unfinished(resume_id)
        return self._session_dto(aggregate) if aggregate is not None else None

    async def find_by_request_id(self, request_id: str) -> InterviewSessionDTO | None:
        aggregate = await self._repository.find_by_request_id(request_id)
        return self._session_dto(aggregate) if aggregate is not None else None

    async def find_unfinished_or_throw(self, resume_id: int) -> InterviewSessionDTO:
        result = await self.find_unfinished_session(resume_id)
        if result is None:
            raise BusinessException(
                ErrorCode.INTERVIEW_SESSION_NOT_FOUND,
                "未找到未完成的面试会话",
            )
        return result

    async def current_question(self, session_id: str) -> dict[str, object]:
        aggregate = await self._required(session_id)
        current = self._current_question(aggregate)
        if current is None:
            return {"completed": True, "message": "所有问题已回答完毕"}
        return {"completed": False, "question": self._question_dto(current)}

    async def submit_turn(
        self,
        session_id: str,
        request: SubmitTurnRequest,
        *,
        remaining_seconds: int | None = None,
    ) -> SubmitTurnResponse:
        answer_hash = self._answer_hash(request.answer)
        cached_turn_id = await self._cache.get_turn_result(session_id, request.request_id)
        if cached_turn_id is not None:
            cached_turn = await self._repository.turn(session_id, UUID(cached_turn_id))
            if cached_turn is not None:
                self._validate_replayed_turn(cached_turn, request, answer_hash)
                if cached_turn.decision_status == TurnDecisionStatus.PROCESSING.value:
                    cached_turn = await self._wait_for_turn(session_id, cached_turn.id)
                if self._metrics is not None:
                    aggregate = await self._required(session_id)
                    self._metrics.interview_duplicate_requests.labels(
                        channel=aggregate.session.channel
                    ).inc()
                    return self._turn_response(aggregate, cached_turn)
                return self._turn_response(await self._required(session_id), cached_turn)
        start = await self._repository.begin_turn(
            session_id,
            request.question_id,
            request.request_id,
            request.answer,
            answer_hash,
            datetime.now() + timedelta(seconds=self._turn_lease_seconds),
        )
        turn = start.turn
        if start.existing:
            if self._metrics is not None:
                self._metrics.interview_duplicate_requests.labels(
                    channel=start.aggregate.session.channel
                ).inc()
            self._validate_replayed_turn(turn, request, answer_hash)
            if turn.decision_status == TurnDecisionStatus.PROCESSING.value:
                turn = await self._wait_for_turn(session_id, turn.id)
            aggregate = await self._required(session_id)
            response = self._turn_response(aggregate, turn)
            await self._cache.set_turn_result(session_id, request.request_id, str(turn.id))
            return response
        try:
            provider = await self._provider(start.aggregate.session.llm_provider)
            decision = await self._decisions.decide(
                provider,
                start.aggregate,
                request.answer,
                remaining_seconds=remaining_seconds,
            )
        except Exception as error:
            logger.exception(
                "failed to resolve turn provider sessionId=%s turnId=%s",
                session_id,
                turn.id,
            )
            decision = self._decisions.fallback_without_model(
                start.aggregate,
                reason_code="PROVIDER_UNAVAILABLE",
                error=str(error),
            )
        finalized = await self._finalize(session_id, turn.id, decision)
        self._record_decision(finalized, decision)
        if finalized.evaluation_pending:
            await self._enqueue_evaluation(session_id)
        await self._cache.set_turn_result(session_id, request.request_id, str(turn.id))
        return self._turn_response(finalized.aggregate, finalized.turn)

    async def complete(self, session_id: str) -> None:
        aggregate = await self._required(session_id)
        processing = next(
            (
                turn
                for turn in aggregate.turns
                if turn.decision_status == TurnDecisionStatus.PROCESSING.value
            ),
            None,
        )
        if processing is not None:
            await self.recover_turn(session_id, processing.id)
        if await self._repository.complete_session(session_id):
            await self._enqueue_evaluation(session_id)

    async def report(self, session_id: str) -> InterviewReportDTO:
        report = await self._repository.saved_report(session_id)
        if report is None:
            aggregate = await self._required(session_id)
            if aggregate.session.status not in {"COMPLETED", "EVALUATED"}:
                raise BusinessException(ErrorCode.INTERVIEW_NOT_COMPLETED)
            raise BusinessException(
                ErrorCode.INTERVIEW_EVALUATION_FAILED,
                "面试报告尚未生成完成",
            )
        return report

    async def regenerate_report(self, session_id: str) -> None:
        aggregate = await self._required(session_id)
        if aggregate.session.status not in {"COMPLETED", "EVALUATED"}:
            raise BusinessException(ErrorCode.INTERVIEW_NOT_COMPLETED)
        await self._repository.update_evaluate_status(session_id, "PENDING", None)
        await self._enqueue_evaluation(session_id)

    async def detail(self, session_id: str) -> InterviewDetailDTO:
        aggregate = await self._required(session_id)
        turn_by_question = {turn.question_id: turn for turn in aggregate.turns}
        report = await self._repository.saved_report(session_id)
        evaluations = {
            detail.question_id: detail
            for group in (report.question_groups if report is not None else [])
            for detail in (group.main_question, *group.follow_ups)
        }
        return InterviewDetailDTO(
            id=aggregate.session.id,
            session_id=session_id,
            channel=InterviewChannel(aggregate.session.channel),
            planned_main_questions=aggregate.session.planned_main_question_count,
            status=str(aggregate.session.status),
            evaluate_status=aggregate.session.evaluate_status,
            evaluate_error=aggregate.session.evaluate_error,
            overall_score=aggregate.session.overall_score,
            knowledge_base_id=aggregate.session.knowledge_base_id,
            overall_feedback=aggregate.session.overall_feedback,
            created_at=aggregate.session.created_at,
            completed_at=aggregate.session.completed_at,
            strengths=parse_saved_list(aggregate.session.strengths_json),
            improvements=parse_saved_list(aggregate.session.improvements_json),
            answers=[
                AnswerDetailDTO(
                    question_id=question.id,
                    parent_question_id=question.parent_question_id,
                    kind=QuestionKind(question.kind),
                    question=question.question,
                    category=question.category,
                    user_answer=(
                        turn_by_question[question.id].answer
                        if question.id in turn_by_question
                        else None
                    ),
                    score=(evaluations[question.id].score if question.id in evaluations else 0),
                    feedback=(
                        evaluations[question.id].feedback if question.id in evaluations else None
                    ),
                    reference_answer=(
                        evaluations[question.id].reference_answer
                        if question.id in evaluations
                        else question.reference_answer
                    ),
                    key_points=(
                        evaluations[question.id].key_points if question.id in evaluations else []
                    ),
                    answered_at=(
                        turn_by_question[question.id].answered_at
                        if question.id in turn_by_question
                        else None
                    ),
                )
                for question in aggregate.questions
            ],
        )

    async def export_pdf(self, session_id: str) -> tuple[bytes, dict[str, str]]:
        aggregate = await self._required(session_id)
        report = await self.report(session_id)
        font = Path(__file__).resolve().parents[4] / "resources/fonts/ZhuqueFangsong-Regular.ttf"
        sections: list[tuple[str, list[str]]] = [
            (
                "面试信息",
                [
                    f"会话ID: {session_id}",
                    f"主问题数量: {aggregate.session.planned_main_question_count}",
                    f"面试状态: {aggregate.session.status}",
                    f"开始时间: {aggregate.session.created_at:%Y-%m-%d %H:%M:%S}",
                ],
            ),
            ("综合评分", [f"总分: {report.overall_score} / 100"]),
            ("总体评价", [report.overall_feedback]),
            ("表现优势", [f"• {item}" for item in report.strengths]),
            ("改进建议", [f"• {item}" for item in report.improvements]),
        ]
        details: list[str] = []
        for index, group in enumerate(report.question_groups, start=1):
            details.extend(
                (
                    f"主问题 {index} [{group.category or '综合'}]",
                    f"Q: {group.main_question.question}",
                    f"A: {group.main_question.answer or '未回答'}",
                    f"问题组得分: {group.group_score}/100",
                    f"评价: {group.group_feedback}",
                )
            )
            for follow_up in group.follow_ups:
                details.extend(
                    (
                        f"追问: {follow_up.question}",
                        f"回答: {follow_up.answer or '未回答'}",
                        f"反馈: {follow_up.feedback}",
                    )
                )
        sections.append(("问答详情", details))
        pdf = await self._blocking_executor.run(
            PdfDocumentBuilder(font).build,
            "模拟面试报告",
            sections,
        )
        return pdf, pdf_download_headers(f"模拟面试报告_{session_id}.pdf")

    async def delete(self, session_id: str) -> None:
        await self._repository.delete_session(session_id)

    async def recover_turn(self, session_id: str, turn_id: UUID) -> bool:
        aggregate = await self._repository.find_session(session_id)
        if aggregate is None:
            return False
        turn = next((item for item in aggregate.turns if item.id == turn_id), None)
        if turn is None or turn.decision_status != TurnDecisionStatus.PROCESSING.value:
            return False
        decision = self._decisions.fallback_for_stale(aggregate)
        finalized = await self._finalize(session_id, turn_id, decision)
        if finalized.evaluation_pending:
            await self._enqueue_evaluation(session_id)
        return True

    async def _create_idempotent(
        self,
        request: CreateInterviewRequest,
        request_id: str,
    ) -> InterviewSessionDTO:
        cached_session_id = await self._cache.get_create_result(request_id)
        if cached_session_id is not None:
            return await self.get_session(cached_session_id)
        existing = await self._repository.find_by_request_id(request_id)
        if existing is not None:
            await self._cache.set_create_result(request_id, existing.session.session_id)
            return self._session_dto(existing)
        created = await self._create_session_internal(request, request_id)
        await self._cache.set_create_result(request_id, created.session_id)
        return created

    async def _create_session_internal(
        self,
        request: CreateInterviewRequest,
        request_id: str | None,
    ) -> InterviewSessionDTO:
        if request.resume_id is not None and request.force_create is not True:
            unfinished = await self.find_unfinished_session(request.resume_id)
            if unfinished is not None:
                return unfinished
        skill_id = request.skill_id or "java-backend"
        difficulty = request.difficulty or "mid"
        historical = [
            HistoricalQuestion(question=item[0], type=item[1], topic_summary=item[2])
            for item in await self._repository.historical_questions(
                skill_id,
                request.resume_id,
            )
        ]
        resume_text = request.resume_text or await self._repository.resume_text(request.resume_id)
        questions = await self._questions.generate(
            provider_id=request.llm_provider,
            skill_id=skill_id,
            difficulty=difficulty,
            resume_text=resume_text,
            question_count=request.question_count,
            historical_questions=historical,
            custom_categories=request.custom_categories,
            jd_text=request.jd_text,
        )
        return await self.create_session_from_questions(
            questions,
            channel=InterviewChannel.TEXT,
            max_follow_ups_per_main=self._follow_up_count,
            llm_provider=request.llm_provider,
            skill_id=skill_id,
            difficulty=difficulty,
            request_id=request_id,
            resume_id=request.resume_id,
            context={"jdText": request.jd_text or ""},
        )

    async def _wait_for_turn(self, session_id: str, turn_id: UUID) -> InterviewTurnRecord:
        deadline = asyncio.get_running_loop().time() + self._turn_wait_seconds
        while asyncio.get_running_loop().time() < deadline:
            turn = await self._repository.turn(session_id, turn_id)
            if turn is None:
                raise BusinessException(ErrorCode.INTERVIEW_QUESTION_NOT_FOUND)
            if turn.decision_status != TurnDecisionStatus.PROCESSING.value:
                return turn
            if turn.lease_expires_at <= datetime.now():
                await self.recover_turn(session_id, turn_id)
            await asyncio.sleep(0.1)
        raise BusinessException(
            ErrorCode.INTERNAL_ERROR,
            "本轮仍在处理中，请稍后重试",
        )

    async def _finalize(
        self,
        session_id: str,
        turn_id: UUID,
        decision: TurnDecisionResult,
    ) -> FinalizeTurn:
        return await self._repository.finalize_turn(
            session_id,
            turn_id,
            action=decision.action,
            acknowledgement=decision.acknowledgement,
            follow_up_question=decision.follow_up_question,
            decision_reason=decision.reason,
            reason_code=decision.reason_code,
            target_topic=decision.target_topic,
            confidence=decision.confidence,
            decision_status=decision.status,
            provider_id=decision.provider_id,
            model_name=decision.model_name,
            prompt_tokens=decision.prompt_tokens,
            completion_tokens=decision.completion_tokens,
            total_tokens=decision.total_tokens,
            duration_ms=decision.duration_ms,
            error=decision.error,
        )

    async def _enqueue_evaluation(self, session_id: str) -> None:
        try:
            await self._streams.add(
                INTERVIEW_EVALUATE.key,
                {FIELD_SESSION_ID: session_id, FIELD_RETRY_COUNT: "0"},
            )
        except Exception:
            logger.exception("failed to queue interview evaluation sessionId=%s", session_id)

    def _record_decision(
        self,
        finalized: FinalizeTurn,
        decision: TurnDecisionResult,
    ) -> None:
        logger.info(
            "interview turn decided sessionId=%s questionId=%s turnId=%s "
            "channel=%s action=%s reasonCode=%s providerId=%s durationMs=%s fallback=%s",
            finalized.aggregate.session.session_id,
            finalized.turn.question_id,
            finalized.turn.id,
            finalized.aggregate.session.channel,
            finalized.turn.action,
            decision.reason_code,
            decision.provider_id,
            decision.duration_ms,
            decision.status == TurnDecisionStatus.FALLBACK,
        )
        if self._metrics is None or finalized.turn.action is None:
            return
        channel = finalized.aggregate.session.channel
        self._metrics.interview_turn_duration.labels(channel=channel).observe(
            decision.duration_ms / 1000
        )
        self._metrics.interview_turn_decisions.labels(
            channel=channel,
            action=finalized.turn.action,
        ).inc()
        if finalized.turn.action == TurnAction.FOLLOW_UP.value:
            self._metrics.interview_follow_ups.labels(channel=channel).inc()
        if decision.status == TurnDecisionStatus.FALLBACK:
            self._metrics.interview_turn_fallbacks.labels(
                channel=channel,
                reason=decision.reason_code,
            ).inc()
        if decision.prompt_tokens is not None:
            self._metrics.interview_turn_tokens.labels(
                channel=channel,
                type="prompt",
            ).inc(decision.prompt_tokens)
        if decision.completion_tokens is not None:
            self._metrics.interview_turn_tokens.labels(
                channel=channel,
                type="completion",
            ).inc(decision.completion_tokens)

    async def _required(self, session_id: str) -> SessionAggregate:
        aggregate = await self._repository.find_session(session_id)
        if aggregate is None:
            raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)
        return aggregate

    async def _provider(self, provider_id: str | None) -> ProviderConfig:
        return await self._registry.get_chat(normalize_provider_alias(provider_id))

    @staticmethod
    def _validate_replayed_turn(
        turn: InterviewTurnRecord,
        request: SubmitTurnRequest,
        answer_hash: str,
    ) -> None:
        if turn.question_id != request.question_id or turn.answer_hash != answer_hash:
            raise BusinessException(
                ErrorCode.BAD_REQUEST,
                "requestId已用于不同的面试回答",
            )

    @staticmethod
    def _answer_hash(answer: str | None) -> str:
        return hashlib.sha256((answer or "").encode()).hexdigest()

    @classmethod
    def _session_dto(cls, aggregate: SessionAggregate) -> InterviewSessionDTO:
        return InterviewSessionDTO(
            session_id=aggregate.session.session_id,
            channel=InterviewChannel(aggregate.session.channel),
            status=InterviewSessionStatus(str(aggregate.session.status)),
            current_question=(
                cls._question_dto(current)
                if (current := cls._current_question(aggregate)) is not None
                else None
            ),
            turns=[
                cls._turn_dto(
                    turn,
                    next(
                        question
                        for question in aggregate.questions
                        if question.id == turn.question_id
                    ),
                )
                for turn in aggregate.turns
            ],
            progress=cls._progress(aggregate),
            knowledge_base_id=aggregate.session.knowledge_base_id,
            interview_category=aggregate.session.interview_category,
        )

    @classmethod
    def _turn_response(
        cls,
        aggregate: SessionAggregate,
        turn: InterviewTurnRecord,
    ) -> SubmitTurnResponse:
        action = TurnAction(str(turn.action))
        next_question = next(
            (question for question in aggregate.questions if question.id == turn.next_question_id),
            None,
        )
        return SubmitTurnResponse(
            turn_id=turn.id,
            action=action,
            acknowledgement=turn.acknowledgement or "",
            next_question=(cls._question_dto(next_question) if next_question is not None else None),
            completed=action == TurnAction.COMPLETE,
            progress=cls._progress(aggregate),
        )

    @staticmethod
    def _question_dto(question: InterviewQuestionRecord) -> InterviewQuestionDTO:
        return InterviewQuestionDTO(
            question_id=question.id,
            kind=QuestionKind(question.kind),
            parent_question_id=question.parent_question_id,
            question=question.question,
            type=question.type,
            category=question.category,
            topic_summary=question.topic_summary,
            phase=question.phase,
        )

    @staticmethod
    def _turn_dto(
        turn: InterviewTurnRecord,
        question: InterviewQuestionRecord,
    ) -> InterviewTurnDTO:
        return InterviewTurnDTO(
            turn_id=turn.id,
            question_id=turn.question_id,
            question=InterviewService._question_dto(question),
            answer=turn.answer,
            action=TurnAction(turn.action) if turn.action is not None else None,
            acknowledgement=turn.acknowledgement,
            next_question_id=turn.next_question_id,
            decision_status=TurnDecisionStatus(turn.decision_status),
            answered_at=turn.answered_at,
            decided_at=turn.decided_at,
        )

    @staticmethod
    def _current_question(aggregate: SessionAggregate) -> InterviewQuestionRecord | None:
        return next(
            (
                question
                for question in aggregate.questions
                if question.id == aggregate.session.current_question_id
            ),
            None,
        )

    @classmethod
    def _progress(cls, aggregate: SessionAggregate) -> InterviewProgressDTO:
        question_by_id = {question.id: question for question in aggregate.questions}
        completed_orders = {
            question_by_id[turn.question_id].main_order
            for turn in aggregate.turns
            if turn.question_id in question_by_id
            and turn.action in {TurnAction.NEXT_MAIN.value, TurnAction.COMPLETE.value}
        }
        current = cls._current_question(aggregate)
        used = (
            sum(
                question.kind == QuestionKind.FOLLOW_UP.value
                and question.main_order == current.main_order
                for question in aggregate.questions
            )
            if current is not None
            else 0
        )
        return InterviewProgressDTO(
            completed_main_questions=len(completed_orders),
            planned_main_questions=aggregate.session.planned_main_question_count,
            follow_ups_used_for_current_main=used,
            max_follow_ups_per_main=aggregate.session.max_follow_ups_per_main,
        )


class EvaluatePayload:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id


class InterviewEvaluateHandler:
    def __init__(
        self,
        repository: InterviewRepository,
        streams: RedisStreamService,
        evaluation: UnifiedEvaluationService,
        registry_factory: Callable[[UUID], ProviderRegistry],
    ) -> None:
        self._repository = repository
        self._streams = streams
        self._evaluation = evaluation
        self._registry_factory = registry_factory

    async def parse(self, message: StreamMessage) -> EvaluatePayload | None:
        session_id = message.data.get(FIELD_SESSION_ID)
        return EvaluatePayload(session_id) if session_id is not None else None

    async def should_skip(self, payload: EvaluatePayload) -> bool:
        aggregate = await self._repository.find_session(payload.session_id)
        return aggregate is None or aggregate.session.evaluate_status == "COMPLETED"

    async def try_mark_processing(self, payload: EvaluatePayload) -> bool:
        return await self._repository.update_evaluate_status(
            payload.session_id,
            "PROCESSING",
            None,
        )

    async def process(self, payload: EvaluatePayload) -> None:
        aggregate = await self._repository.find_session(payload.session_id)
        if aggregate is None:
            return
        provider = await self._registry_factory(aggregate.session.user_id).get_chat(
            normalize_provider_alias(aggregate.session.llm_provider)
        )
        provider = opentrek_provider_with_skills(provider, aggregate.session.skill_id)
        report = await self._evaluation.evaluate(provider, aggregate)
        await self._repository.save_report(payload.session_id, report)

    async def mark_completed(self, payload: EvaluatePayload) -> None:
        await self._repository.update_evaluate_status(payload.session_id, "COMPLETED", None)

    async def retry(self, payload: EvaluatePayload, retry_count: int) -> None:
        await self._repository.update_evaluate_status(payload.session_id, "PENDING", None)
        await self._streams.add(
            INTERVIEW_EVALUATE.key,
            {
                FIELD_SESSION_ID: payload.session_id,
                FIELD_RETRY_COUNT: str(retry_count),
            },
        )

    async def mark_failed(self, payload: EvaluatePayload, error: str) -> None:
        await self._repository.update_evaluate_status(payload.session_id, "FAILED", error)


class InterviewRecoveryService:
    def __init__(
        self,
        repository: InterviewRepository,
        service: InterviewService,
        streams: RedisStreamService,
        *,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._repository = repository
        self._service = service
        self._streams = streams
        self._now = now

    async def recover(self) -> tuple[int, int]:
        recovered_turns = 0
        for session_id, turn_id in await self._repository.stale_processing_turns(self._now()):
            recovered_turns += int(await self._service.recover_turn(session_id, turn_id))
        requeued = 0
        threshold = self._now() - timedelta(seconds=30)
        for session_id in await self._repository.pending_evaluations(threshold):
            await self._streams.add(
                INTERVIEW_EVALUATE.key,
                {FIELD_SESSION_ID: session_id, FIELD_RETRY_COUNT: "0"},
            )
            requeued += 1
        return recovered_turns, requeued
