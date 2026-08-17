from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.providers import LlmProviderRegistry
from interview_guide.common.db.models import InterviewAnswer
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.redis.streams import (
    FIELD_RETRY_COUNT,
    FIELD_SESSION_ID,
    INTERVIEW_EVALUATE,
    RedisStreamService,
    StreamMessage,
)
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.infrastructure.export.pdf import (
    PdfDocumentBuilder,
    pdf_download_headers,
)
from interview_guide.modules.interview.cache import (
    CachedSession,
    InterviewSessionCache,
)
from interview_guide.modules.interview.evaluation import AnswerEvaluationService
from interview_guide.modules.interview.models import (
    AnswerDetailDTO,
    CreateInterviewRequest,
    InterviewDetailDTO,
    InterviewQuestion,
    InterviewReportDTO,
    InterviewSessionDTO,
    InterviewSessionStatus,
    SessionListItemDTO,
    SubmitAnswerResponse,
)
from interview_guide.modules.interview.question import InterviewQuestionService
from interview_guide.modules.interview.repository import (
    InterviewRepository,
    SessionRecord,
)

logger = logging.getLogger(__name__)


class InterviewService:
    def __init__(
        self,
        repository: InterviewRepository,
        cache: InterviewSessionCache,
        streams: RedisStreamService,
        questions: InterviewQuestionService,
        evaluation: AnswerEvaluationService,
        registry: LlmProviderRegistry,
        blocking_executor: BlockingExecutor,
        uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._repository = repository
        self._cache = cache
        self._streams = streams
        self._questions = questions
        self._evaluation = evaluation
        self._registry = registry
        self._blocking_executor = blocking_executor
        self._uuid_factory = uuid_factory

    async def list_sessions(self) -> list[SessionListItemDTO]:
        return [
            SessionListItemDTO(
                session_id=entity.session_id,
                skill_id=entity.skill_id,
                difficulty=entity.difficulty,
                resume_id=entity.resume_id,
                total_questions=entity.total_questions or 0,
                status=entity.status,
                evaluate_status=entity.evaluate_status,
                evaluate_error=entity.evaluate_error,
                overall_score=entity.overall_score,
                source_type=entity.source_type,
                knowledge_base_id=entity.knowledge_base_id,
                interview_category=entity.interview_category,
                created_at=entity.created_at,
                completed_at=entity.completed_at,
            )
            for entity in await self._repository.list_sessions()
        ]

    async def create_session(
        self,
        request: CreateInterviewRequest,
    ) -> InterviewSessionDTO:
        request_id = self._normalize_request_id(request.request_id)
        if request_id is None:
            return await self._create_session_internal(request, None)

        async def operation() -> InterviewSessionDTO:
            return await self._create_idempotent(request, request_id)

        return await self._cache.execute_create_locked(request_id, operation)

    async def get_session(self, session_id: str) -> InterviewSessionDTO:
        cached = await self._cache.get_session(session_id)
        if cached is not None:
            return self._to_session_dto(cached)
        restored = await self._restore_from_database(session_id)
        if restored is None:
            raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)
        return self._to_session_dto(restored)

    async def find_unfinished_session(
        self,
        resume_id: int,
    ) -> InterviewSessionDTO | None:
        try:
            cached_session_id = await self._cache.find_unfinished_session_id(resume_id)
            if cached_session_id is not None:
                cached = await self._cache.get_session(cached_session_id)
                if cached is not None:
                    return self._to_session_dto(cached)
            record = await self._repository.find_unfinished(resume_id)
            if record is None:
                return None
            restored = await self._restore_from_record(record)
            return self._to_session_dto(restored) if restored is not None else None
        except Exception:
            logger.exception("failed to restore unfinished interview")
            return None

    async def find_unfinished_or_throw(self, resume_id: int) -> InterviewSessionDTO:
        result = await self.find_unfinished_session(resume_id)
        if result is None:
            raise BusinessException(
                ErrorCode.INTERVIEW_SESSION_NOT_FOUND,
                "未找到未完成的面试会话",
            )
        return result

    async def current_question(self, session_id: str) -> dict[str, object]:
        session = await self._get_or_restore(session_id)
        questions = session.questions
        if session.current_index >= len(questions):
            return {"completed": True, "message": "所有问题已回答完毕"}
        if session.status == InterviewSessionStatus.CREATED:
            await self._cache.update_status(
                session_id,
                InterviewSessionStatus.IN_PROGRESS,
            )
            try:
                await self._repository.update_session_status(
                    session_id,
                    InterviewSessionStatus.IN_PROGRESS.value,
                )
            except Exception:
                logger.warning(
                    "failed to persist interview in-progress status",
                    exc_info=True,
                )
        return {"completed": False, "question": questions[session.current_index]}

    async def submit_answer(
        self,
        session_id: str,
        question_index: int,
        answer: str | None,
    ) -> SubmitAnswerResponse:
        cached = await self._get_or_restore(session_id)
        questions = cached.questions
        self._validate_question_index(question_index, questions)
        original = questions[question_index]
        questions[question_index] = original.with_answer(answer)
        new_index = question_index + 1
        has_next = new_index < len(questions)
        next_question = questions[new_index] if has_next else None
        new_status = (
            InterviewSessionStatus.IN_PROGRESS if has_next else InterviewSessionStatus.COMPLETED
        )
        try:
            await self._repository.save_answer(
                session_id,
                question_index,
                original.question,
                original.category,
                answer,
                0,
                None,
            )
            await self._repository.update_current_question_index(
                session_id,
                new_index,
            )
            await self._repository.update_session_status(
                session_id,
                new_status.value,
            )
        except BusinessException:
            raise
        except Exception as error:
            logger.exception("failed to save submitted interview answer")
            raise BusinessException(
                ErrorCode.INTERVIEW_ANSWER_SAVE_FAILED,
                "保存答案失败，请稍后重试",
            ) from error
        await self._cache.update_questions(session_id, questions)
        await self._cache.update_current_index(session_id, new_index)
        if new_status == InterviewSessionStatus.COMPLETED:
            await self._cache.update_status(session_id, new_status)
            await self._repository.update_evaluate_status(
                session_id,
                "PENDING",
                None,
            )
            await self._enqueue_evaluation(session_id)
        return SubmitAnswerResponse(
            has_next_question=has_next,
            next_question=next_question,
            current_index=new_index,
            total_questions=len(questions),
        )

    async def save_answer(
        self,
        session_id: str,
        question_index: int,
        answer: str | None,
    ) -> None:
        cached = await self._get_or_restore(session_id)
        questions = cached.questions
        self._validate_question_index(question_index, questions)
        original = questions[question_index]
        questions[question_index] = original.with_answer(answer)
        await self._cache.update_questions(session_id, questions)
        if cached.status == InterviewSessionStatus.CREATED:
            await self._cache.update_status(
                session_id,
                InterviewSessionStatus.IN_PROGRESS,
            )
        try:
            await self._repository.save_answer(
                session_id,
                question_index,
                original.question,
                original.category,
                answer,
                0,
                None,
            )
            await self._repository.update_session_status(
                session_id,
                InterviewSessionStatus.IN_PROGRESS.value,
            )
        except Exception:
            logger.warning("failed to persist interview draft", exc_info=True)

    async def complete(self, session_id: str) -> None:
        cached = await self._get_or_restore(session_id)
        if cached.status in {
            InterviewSessionStatus.COMPLETED,
            InterviewSessionStatus.EVALUATED,
        }:
            raise BusinessException(ErrorCode.INTERVIEW_ALREADY_COMPLETED)
        await self._cache.update_status(
            session_id,
            InterviewSessionStatus.COMPLETED,
        )
        try:
            await self._repository.update_session_status(
                session_id,
                InterviewSessionStatus.COMPLETED.value,
            )
            await self._repository.update_evaluate_status(
                session_id,
                "PENDING",
                None,
            )
        except Exception:
            logger.warning("failed to persist interview completion", exc_info=True)
        await self._enqueue_evaluation(session_id)

    async def generate_report(self, session_id: str) -> InterviewReportDTO:
        cached = await self._get_or_restore(session_id)
        if cached.status not in {
            InterviewSessionStatus.COMPLETED,
            InterviewSessionStatus.EVALUATED,
        }:
            raise BusinessException(
                ErrorCode.INTERVIEW_NOT_COMPLETED,
                "面试尚未完成，无法生成报告",
            )
        record = await self._repository.find_session(session_id)
        provider_id = record.session.llm_provider if record is not None else None
        provider = await self._provider(provider_id)
        report = await self._evaluation.evaluate(
            provider,
            session_id,
            cached.resume_text,
            cached.questions,
            record.session.skill_id if record is not None else None,
        )
        await self._cache.update_status(
            session_id,
            InterviewSessionStatus.EVALUATED,
        )
        try:
            await self._repository.save_report(session_id, report)
        except Exception:
            logger.warning("failed to persist interview report", exc_info=True)
        return report

    async def detail(self, session_id: str) -> InterviewDetailDTO:
        record = await self._repository.find_session(session_id)
        if record is None:
            raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)
        entity = record.session
        questions_document = self._parse_json(entity.questions_json)
        all_questions = [
            InterviewQuestion.model_validate(item) for item in questions_document or []
        ]
        answers = await self._repository.answers(session_id)
        answer_by_index = {answer.question_index: answer for answer in answers}
        answer_details: list[AnswerDetailDTO] = []
        if all_questions:
            for question in all_questions:
                answer = answer_by_index.get(question.question_index)
                if answer is None:
                    answer_details.append(
                        AnswerDetailDTO(
                            question_index=question.question_index,
                            question=question.question,
                            category=question.category,
                            user_answer=None,
                            score=question.score or 0,
                            feedback=question.feedback,
                            reference_answer=None,
                            key_points=None,
                            answered_at=None,
                        )
                    )
                else:
                    answer_details.append(self._answer_detail(answer))
        else:
            answer_details = [self._answer_detail(answer) for answer in answers]
        return InterviewDetailDTO(
            id=entity.id,
            session_id=entity.session_id,
            total_questions=entity.total_questions,
            status=str(entity.status),
            evaluate_status=entity.evaluate_status,
            evaluate_error=entity.evaluate_error,
            overall_score=entity.overall_score,
            source_type=entity.source_type,
            knowledge_base_id=entity.knowledge_base_id,
            overall_feedback=entity.overall_feedback,
            created_at=entity.created_at,
            completed_at=entity.completed_at,
            questions=questions_document,
            strengths=self._parse_json(entity.strengths_json),
            improvements=self._parse_json(entity.improvements_json),
            reference_answers=self._parse_json(entity.reference_answers_json),
            answers=answer_details,
        )

    async def export_pdf(self, session_id: str) -> tuple[bytes, dict[str, str]]:
        record = await self._repository.find_session(session_id)
        if record is None:
            raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)
        answers = await self._repository.answers(session_id)
        entity = record.session
        font = Path(__file__).resolve().parents[4] / "resources/fonts/ZhuqueFangsong-Regular.ttf"
        sections: list[tuple[str, list[str]]] = [
            (
                "面试信息",
                [
                    f"会话ID: {entity.session_id}",
                    f"题目数量: {entity.total_questions}",
                    f"面试状态: {self._status_text(str(entity.status))}",
                    f"开始时间: {self._pdf_time(entity.created_at)}",
                    *(
                        [f"完成时间: {self._pdf_time(entity.completed_at)}"]
                        if entity.completed_at is not None
                        else []
                    ),
                ],
            )
        ]
        if entity.overall_score is not None:
            sections.append(("综合评分", [f"总分: {entity.overall_score} / 100"]))
        if entity.overall_feedback is not None:
            sections.append(("总体评价", [entity.overall_feedback]))
        strengths = self._parse_json(entity.strengths_json)
        if strengths:
            sections.append(("表现优势", [f"• {item}" for item in strengths]))
        improvements = self._parse_json(entity.improvements_json)
        if improvements:
            sections.append(("改进建议", [f"• {item}" for item in improvements]))
        if answers:
            paragraphs: list[str] = []
            for answer in answers:
                score = answer.score
                paragraphs.extend(
                    (
                        f"问题 {(answer.question_index or 0) + 1} [{answer.category or '综合'}]",
                        f"Q: {answer.question or ''}",
                        f"A: {answer.user_answer if answer.user_answer is not None else '未回答'}",
                        f"得分: {score}/100",
                    )
                )
                if answer.feedback is not None:
                    paragraphs.append(f"评价: {answer.feedback}")
                if answer.reference_answer is not None:
                    paragraphs.append(f"参考答案: {answer.reference_answer}")
            sections.append(("问答详情", paragraphs))
        pdf = await self._blocking_executor.run(
            PdfDocumentBuilder(font).build,
            "模拟面试报告",
            sections,
        )
        return (
            pdf,
            pdf_download_headers(f"模拟面试报告_{session_id}.pdf"),
        )

    async def delete(self, session_id: str) -> None:
        await self._repository.delete_session(session_id)

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
            await self._cache.set_create_result(
                request_id,
                existing.session.session_id,
            )
            return await self.get_session(existing.session.session_id)
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
        session_id = str(self._uuid_factory()).replace("-", "")[:16]
        skill_id = request.skill_id or "java-backend"
        difficulty = request.difficulty or "mid"
        historical = await self._repository.historical_questions(
            skill_id,
            request.resume_id,
        )
        questions = await self._questions.generate(
            provider_id=request.llm_provider,
            skill_id=skill_id,
            difficulty=difficulty,
            resume_text=request.resume_text,
            question_count=request.question_count,
            historical_questions=historical,
            custom_categories=request.custom_categories,
            jd_text=request.jd_text,
        )
        if request_id is not None:
            try:
                await self._repository.create_session(
                    session_id=session_id,
                    resume_id=request.resume_id,
                    questions=questions,
                    llm_provider=request.llm_provider,
                    skill_id=skill_id,
                    difficulty=difficulty,
                    request_id=request_id,
                )
            except Exception as error:
                concurrently_created = await self._repository.find_by_request_id(request_id)
                if concurrently_created is not None:
                    return await self.get_session(concurrently_created.session.session_id)
                raise BusinessException(
                    ErrorCode.INTERNAL_ERROR,
                    "创建面试会话失败，请重试",
                ) from error
        else:
            try:
                await self._repository.create_session(
                    session_id=session_id,
                    resume_id=request.resume_id,
                    questions=questions,
                    llm_provider=request.llm_provider,
                    skill_id=skill_id,
                    difficulty=difficulty,
                    request_id=None,
                )
            except Exception:
                logger.warning("failed to persist interview session", exc_info=True)
        resume_text = request.resume_text or ""
        await self._cache.save_session(
            session_id,
            resume_text,
            request.resume_id,
            None,
            None,
            questions,
            0,
            InterviewSessionStatus.CREATED,
        )
        return InterviewSessionDTO(
            session_id=session_id,
            resume_text=resume_text,
            total_questions=len(questions),
            current_question_index=0,
            questions=questions,
            status=InterviewSessionStatus.CREATED,
            knowledge_base_id=None,
            interview_category=None,
        )

    async def _get_or_restore(self, session_id: str) -> CachedSession:
        cached = await self._cache.get_session(session_id)
        if cached is not None:
            await self._cache.refresh_session_ttl(session_id)
            return cached
        restored = await self._restore_from_database(session_id)
        if restored is None:
            raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)
        return restored

    async def _restore_from_database(
        self,
        session_id: str,
    ) -> CachedSession | None:
        try:
            record = await self._repository.find_session(session_id)
            return await self._restore_from_record(record) if record is not None else None
        except Exception:
            logger.exception("failed to restore interview session")
            return None

    async def _restore_from_record(
        self,
        record: SessionRecord,
    ) -> CachedSession | None:
        try:
            entity = record.session
            questions = [
                InterviewQuestion.model_validate(item)
                for item in json.loads(entity.questions_json or "[]")
            ]
            for answer in await self._repository.answers(entity.session_id):
                index = answer.question_index
                if index is not None and 0 <= index < len(questions):
                    questions[index] = questions[index].with_answer(answer.user_answer)
            status = InterviewSessionStatus(str(entity.status))
            await self._cache.save_session(
                entity.session_id,
                record.resume_text,
                entity.resume_id,
                entity.knowledge_base_id,
                entity.interview_category,
                questions,
                entity.current_question_index or 0,
                status,
            )
            return await self._cache.get_session(entity.session_id)
        except Exception:
            logger.exception("failed to restore interview session record")
            return None

    async def _enqueue_evaluation(self, session_id: str) -> None:
        try:
            await self._streams.add(
                INTERVIEW_EVALUATE.key,
                {
                    FIELD_SESSION_ID: session_id,
                    FIELD_RETRY_COUNT: "0",
                },
            )
        except Exception as error:
            await self._repository.update_evaluate_status(
                session_id,
                "FAILED",
                f"任务入队失败: {error}"[:500],
            )

    async def _provider(self, provider_id: str | None) -> ProviderConfig:
        return await self._registry.get_chat(
            None if provider_id in {None, "", "default"} else provider_id
        )

    @staticmethod
    def _normalize_request_id(value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        if (
            len(normalized) < 8
            or len(normalized) > 64
            or any(
                not (character.isascii() and (character.isalnum() or character in "_-"))
                for character in normalized
            )
        ):
            raise BusinessException(
                ErrorCode.BAD_REQUEST,
                "requestId 格式不正确",
            )
        return normalized

    @staticmethod
    def _validate_question_index(
        question_index: int,
        questions: list[InterviewQuestion],
    ) -> None:
        if question_index < 0 or question_index >= len(questions):
            raise BusinessException(
                ErrorCode.INTERVIEW_QUESTION_NOT_FOUND,
                f"无效的问题索引: {question_index}",
            )

    @staticmethod
    def _to_session_dto(cached: CachedSession) -> InterviewSessionDTO:
        questions = cached.questions
        return InterviewSessionDTO(
            session_id=cached.session_id,
            resume_text=cached.resume_text,
            total_questions=len(questions),
            current_question_index=cached.current_index,
            questions=questions,
            status=cached.status,
            knowledge_base_id=cached.knowledge_base_id,
            interview_category=cached.interview_category,
        )

    @staticmethod
    def _parse_json(value: str | None) -> Any:
        if value is None:
            return None
        try:
            return json.loads(value)
        except Exception:
            logger.exception("failed to parse persisted interview JSON")
            return None

    @staticmethod
    def _answer_detail(answer: InterviewAnswer) -> AnswerDetailDTO:
        key_points_json = answer.key_points_json
        key_points = json.loads(key_points_json) if key_points_json is not None else None
        return AnswerDetailDTO(
            question_index=answer.question_index,
            question=answer.question,
            category=answer.category,
            user_answer=answer.user_answer,
            score=answer.score or 0,
            feedback=answer.feedback,
            reference_answer=answer.reference_answer,
            key_points=key_points,
            answered_at=answer.answered_at,
        )

    @staticmethod
    def _status_text(status: str) -> str:
        return {
            "CREATED": "已创建",
            "IN_PROGRESS": "进行中",
            "COMPLETED": "已完成",
            "EVALUATED": "已评估",
        }[status]

    @staticmethod
    def _pdf_time(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


class EvaluatePayload:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id


class InterviewEvaluateHandler:
    def __init__(
        self,
        repository: InterviewRepository,
        streams: RedisStreamService,
        evaluation: AnswerEvaluationService,
        registry: LlmProviderRegistry,
    ) -> None:
        self._repository = repository
        self._streams = streams
        self._evaluation = evaluation
        self._registry = registry

    async def parse(self, message: StreamMessage) -> EvaluatePayload | None:
        session_id = message.data.get(FIELD_SESSION_ID)
        return EvaluatePayload(session_id) if session_id is not None else None

    async def should_skip(self, payload: EvaluatePayload) -> bool:
        record = await self._repository.find_session(payload.session_id)
        return record is None or record.session.evaluate_status == "COMPLETED"

    async def try_mark_processing(self, payload: EvaluatePayload) -> bool:
        await self._repository.update_evaluate_status(
            payload.session_id,
            "PROCESSING",
            None,
        )
        return True

    async def process(self, payload: EvaluatePayload) -> None:
        record = await self._repository.find_session(payload.session_id)
        if record is None:
            return
        entity = record.session
        questions = [
            InterviewQuestion.model_validate(item)
            for item in json.loads(entity.questions_json or "[]")
        ]
        for answer in await self._repository.answers(payload.session_id):
            index = answer.question_index
            if index is not None and 0 <= index < len(questions):
                questions[index] = questions[index].with_answer(answer.user_answer)
        provider = await self._registry.get_chat(
            None if entity.llm_provider in {None, "", "default"} else entity.llm_provider
        )
        report = await self._evaluation.evaluate(
            provider,
            payload.session_id,
            record.resume_text,
            questions,
            entity.skill_id,
        )
        await self._repository.save_report(payload.session_id, report)

    async def mark_completed(self, payload: EvaluatePayload) -> None:
        await self._repository.update_evaluate_status(
            payload.session_id,
            "COMPLETED",
            None,
        )

    async def retry(self, payload: EvaluatePayload, retry_count: int) -> None:
        try:
            await self._streams.add(
                INTERVIEW_EVALUATE.key,
                {
                    FIELD_SESSION_ID: payload.session_id,
                    FIELD_RETRY_COUNT: str(retry_count),
                },
            )
        except Exception as error:
            await self._repository.update_evaluate_status(
                payload.session_id,
                "FAILED",
                f"重试入队失败: {error}"[:500],
            )
            raise

    async def mark_failed(
        self,
        payload: EvaluatePayload,
        error: str,
    ) -> None:
        await self._repository.update_evaluate_status(
            payload.session_id,
            "FAILED",
            error,
        )
