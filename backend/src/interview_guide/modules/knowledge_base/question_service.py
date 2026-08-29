from __future__ import annotations

import json
import logging
import random
import unicodedata
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Any, Protocol, cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.ai.adapter import LlmAdapter, ProviderConfig
from interview_guide.common.ai.opentrek import (
    OpenTrekProviderConfig,
    opentrek_provider_for_kb_question_generation,
)
from interview_guide.common.ai.prompts import (
    DATA_BOUNDARY_INSTRUCTION,
    PromptRepository,
    PromptSanitizer,
)
from interview_guide.common.ai.providers import ProviderRegistry
from interview_guide.common.ai.structured import StructuredOutputInvoker, structured_output_format
from interview_guide.common.api.models import compact_json_text
from interview_guide.common.db.models import KnowledgeBaseQuestion
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.redis.streams import (
    FIELD_KB_ID,
    FIELD_RETRY_COUNT,
    FIELD_TASK_ID,
    KB_QUESTION_GEN,
    RedisStreamService,
    StreamMessage,
)
from interview_guide.modules.interview.models import (
    InterviewChannel,
    InterviewSessionDTO,
    PlannedInterviewQuestion,
)
from interview_guide.modules.interview.service import InterviewService
from interview_guide.modules.knowledge_base.query_service import QueryRetriever
from interview_guide.modules.knowledge_base.question_models import (
    CategoryCount,
    CreateKnowledgeBaseInterviewRequest,
    CreateKnowledgeBaseQuestionRequest,
    GeneratedQuestion,
    GeneratedQuestionList,
    GenerateKnowledgeBaseQuestionsRequest,
    InterviewCategoryCapacity,
    InterviewFollowUpCapacity,
    KnowledgeBaseInterviewCapacityResponse,
    KnowledgeBaseQuestionDTO,
    KnowledgeBaseQuestionFollowUp,
    KnowledgeBaseQuestionStatus,
    QuestionGenerationConfig,
    QuestionGenStatus,
    QuestionGenStatusResponse,
    UpdateKnowledgeBaseQuestionRequest,
)
from interview_guide.modules.knowledge_base.question_repository import (
    KnowledgeBaseQuestionRepository,
    QuestionRow,
)
from interview_guide.modules.knowledge_base.repository import KnowledgeBaseQueryRepository

logger = logging.getLogger(__name__)
DEFAULT_SKILL_ID = "knowledge-base"
DEFAULT_DIFFICULTY = "mid"
DEFAULT_FOLLOW_UP_COUNT = 2
DEFAULT_CATEGORY_LIMIT = 3
SAFE_FAILURE_MESSAGE = "题目生成失败，请稍后重试"
MAX_FOLLOW_UP_COUNT = 5
RETRIEVAL_TOP_K = 12
RETRIEVAL_QUERY_TOP_K = 4
MAX_CONTEXT_CHARS = 5000
GENERATION_QUERIES = (
    "核心概念 定义 背景 原理",
    "关键流程 步骤 方法 工作机制",
    "规则约束 条件 边界 例外 限制",
    "典型案例 常见问题 应用场景 最佳实践",
)

QUESTION_OUTPUT_FORMAT = structured_output_format(
    {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "followUps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "keyPoints": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "question": {"type": "string"},
                                    "referenceAnswer": {"type": "string"},
                                    "scoringRubric": {"type": "string"},
                                },
                                "required": [
                                    "keyPoints",
                                    "question",
                                    "referenceAnswer",
                                    "scoringRubric",
                                ],
                                "additionalProperties": False,
                            },
                        },
                        "keyPoints": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "question": {"type": "string"},
                        "referenceAnswer": {"type": "string"},
                        "scoringRubric": {"type": "string"},
                        "topicSummary": {"type": "string"},
                        "type": {"type": "string"},
                    },
                    "required": [
                        "category",
                        "followUps",
                        "keyPoints",
                        "question",
                        "referenceAnswer",
                        "scoringRubric",
                        "topicSummary",
                        "type",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["questions"],
        "additionalProperties": False,
    }
)


def trim_to_none(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()


def normalize_difficulty(value: str | None) -> str:
    return value.strip() if value is not None and value.strip() else DEFAULT_DIFFICULTY


def sanitized_strings(values: Sequence[str | None] | None) -> list[str]:
    return [value.strip() for value in values or () if value is not None and value.strip()]


def parse_string_list(value: str | None) -> list[str]:
    if value is None or not value.strip():
        return []
    try:
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            return []
        return [str(item) for item in parsed if isinstance(item, str)]
    except (TypeError, ValueError):
        logger.warning("failed to parse question string list")
        return []


def parse_follow_ups(value: str | None) -> list[KnowledgeBaseQuestionFollowUp]:
    if value is None or not value.strip():
        return []
    try:
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            return []
        result: list[KnowledgeBaseQuestionFollowUp] = []
        for item in parsed:
            if isinstance(item, dict):
                result.append(KnowledgeBaseQuestionFollowUp.model_validate(item))
            else:
                raise ValueError("invalid follow-up")
        return result
    except (TypeError, ValueError):
        logger.warning("failed to parse question follow-ups")
        return []


def sanitize_follow_ups(
    values: Sequence[KnowledgeBaseQuestionFollowUp | None] | None,
    *,
    limit: int | None = None,
) -> list[dict[str, object]]:
    if limit is not None and limit <= 0:
        return []
    result: list[dict[str, object]] = []
    for value in values or ():
        if value is None or value.question is None or not value.question.strip():
            continue
        result.append(
            {
                "question": value.question.strip(),
                "referenceAnswer": trim_to_none(value.reference_answer),
                "keyPoints": sanitized_strings(value.key_points),
                "scoringRubric": trim_to_none(value.scoring_rubric),
            }
        )
        if limit is not None and len(result) >= limit:
            break
    return result


def question_dto(row: QuestionRow) -> KnowledgeBaseQuestionDTO:
    entity = row.question
    return KnowledgeBaseQuestionDTO(
        id=entity.id,
        knowledge_base_id=entity.knowledge_base_id,
        knowledge_base_name=row.knowledge_base_name,
        skill_id=entity.skill_id,
        difficulty=entity.difficulty,
        type=entity.type,
        category=entity.category,
        question=entity.question,
        topic_summary=entity.topic_summary,
        reference_answer=entity.reference_answer,
        key_points=parse_string_list(entity.key_points_json),
        scoring_rubric=entity.scoring_rubric,
        follow_ups=parse_follow_ups(entity.follow_ups_json),
        source_context=entity.source_context,
        status=KnowledgeBaseQuestionStatus(entity.status),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


class QuestionGenerationStateService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        now: Callable[[], datetime] = datetime.now,
        task_id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
        user_id: uuid.UUID | None = None,
    ) -> None:
        self._sessions = sessions
        self._now = now
        self._task_id_factory = task_id_factory
        self._user_id = user_id

    async def create_task(
        self,
        knowledge_base_id: int,
        config: QuestionGenerationConfig,
    ) -> QuestionGenStatusResponse:
        async with self._sessions() as session, session.begin():
            repository = KnowledgeBaseQuestionRepository(session, self._user_id)
            entity = await repository.knowledge_base(knowledge_base_id, for_update=True)
            if entity is None:
                raise BusinessException(ErrorCode.KNOWLEDGE_BASE_NOT_FOUND)
            if entity.vector_status != "COMPLETED":
                raise BusinessException(ErrorCode.BAD_REQUEST, "知识库尚未完成向量化")
            if entity.question_gen_status in {"QUEUED", "PROCESSING"}:
                raise BusinessException(
                    ErrorCode.BAD_REQUEST,
                    "知识库问题正在生成中，请勿重复提交",
                )
            entity.question_gen_task_id = self._task_id_factory()
            entity.question_gen_status = "QUEUED"
            entity.question_gen_config = compact_json_text(config.model_dump(by_alias=True))
            entity.question_gen_error = None
            entity.question_gen_message = None
            entity.question_gen_saved_count = 0
            entity.question_gen_skipped_count = 0
            entity.question_gen_updated_at = self._now()
            return self._response(entity, config)

    async def get_status(self, knowledge_base_id: int) -> QuestionGenStatusResponse:
        async with self._sessions() as session:
            entity = await KnowledgeBaseQuestionRepository(session, self._user_id).knowledge_base(
                knowledge_base_id
            )
            if entity is None:
                raise BusinessException(ErrorCode.KNOWLEDGE_BASE_NOT_FOUND)
            return self._response(entity, self._read_config(entity.question_gen_config))

    async def get_config(
        self,
        knowledge_base_id: int,
        task_id: str,
    ) -> QuestionGenerationConfig:
        async with self._sessions() as session:
            entity = await KnowledgeBaseQuestionRepository(session, self._user_id).knowledge_base(
                knowledge_base_id
            )
            if entity is None:
                raise BusinessException(ErrorCode.KNOWLEDGE_BASE_NOT_FOUND)
            if task_id != entity.question_gen_task_id:
                raise BusinessException(ErrorCode.BAD_REQUEST, "题目生成任务已失效")
            config = self._read_config(entity.question_gen_config)
            if config is None:
                raise BusinessException(ErrorCode.INTERNAL_ERROR, "题目生成配置不存在")
            return config

    async def try_mark_processing(self, knowledge_base_id: int, task_id: str) -> bool:
        async with self._sessions() as session, session.begin():
            entity = await KnowledgeBaseQuestionRepository(session, self._user_id).knowledge_base(
                knowledge_base_id,
                for_update=True,
            )
            if not self._matches(entity, task_id, "QUEUED"):
                return False
            assert entity is not None
            entity.question_gen_status = "PROCESSING"
            entity.question_gen_error = None
            entity.question_gen_updated_at = self._now()
            return True

    async def reset_for_retry(self, knowledge_base_id: int, task_id: str) -> bool:
        return await self._transition(
            knowledge_base_id,
            task_id,
            "PROCESSING",
            "QUEUED",
        )

    async def mark_failed(self, knowledge_base_id: int, task_id: str) -> bool:
        async with self._sessions() as session, session.begin():
            entity = await KnowledgeBaseQuestionRepository(session, self._user_id).knowledge_base(
                knowledge_base_id,
                for_update=True,
            )
            if entity is None or entity.question_gen_task_id != task_id:
                return False
            if entity.question_gen_status == "COMPLETED":
                return False
            entity.question_gen_status = "FAILED"
            entity.question_gen_error = SAFE_FAILURE_MESSAGE
            entity.question_gen_updated_at = self._now()
            return True

    async def replace_questions_and_complete(
        self,
        knowledge_base_id: int,
        task_id: str,
        questions: list[KnowledgeBaseQuestion],
        skipped_count: int,
    ) -> bool:
        async with self._sessions() as session, session.begin():
            repository = KnowledgeBaseQuestionRepository(session, self._user_id)
            entity = await repository.knowledge_base(knowledge_base_id, for_update=True)
            if not self._matches(entity, task_id, "PROCESSING"):
                return False
            await repository.replace_questions(knowledge_base_id, questions)
            assert entity is not None
            saved_count = len(questions)
            entity.question_gen_status = "COMPLETED"
            entity.question_gen_error = None
            entity.question_gen_message = (
                f"已生成 {saved_count} 道题，跳过 {skipped_count} 道重复题"
                if skipped_count > 0
                else f"已生成 {saved_count} 道题"
            )
            entity.question_gen_saved_count = saved_count
            entity.question_gen_skipped_count = skipped_count
            entity.question_gen_updated_at = self._now()
            return True

    async def touch_queued_for_recovery(
        self,
        knowledge_base_id: int,
        task_id: str,
        threshold: datetime,
    ) -> bool:
        return await self._recover_transition(
            knowledge_base_id,
            task_id,
            "QUEUED",
            "QUEUED",
            threshold,
        )

    async def reset_stale_processing(
        self,
        knowledge_base_id: int,
        task_id: str,
        threshold: datetime,
    ) -> bool:
        return await self._recover_transition(
            knowledge_base_id,
            task_id,
            "PROCESSING",
            "QUEUED",
            threshold,
        )

    async def stale_tasks(
        self,
        status: QuestionGenStatus,
        threshold: datetime,
    ) -> list[tuple[int, str | None]]:
        async with self._sessions() as session:
            return await KnowledgeBaseQuestionRepository(
                session, self._user_id
            ).stale_generation_tasks(
                status.value,
                threshold,
            )

    async def _transition(
        self,
        knowledge_base_id: int,
        task_id: str,
        expected: str,
        target: str,
    ) -> bool:
        async with self._sessions() as session, session.begin():
            entity = await KnowledgeBaseQuestionRepository(session, self._user_id).knowledge_base(
                knowledge_base_id,
                for_update=True,
            )
            if not self._matches(entity, task_id, expected):
                return False
            assert entity is not None
            entity.question_gen_status = target
            entity.question_gen_updated_at = self._now()
            return True

    async def _recover_transition(
        self,
        knowledge_base_id: int,
        task_id: str,
        expected: str,
        target: str,
        threshold: datetime,
    ) -> bool:
        async with self._sessions() as session, session.begin():
            entity = await KnowledgeBaseQuestionRepository(session, self._user_id).knowledge_base(
                knowledge_base_id,
                for_update=True,
            )
            if not self._matches(entity, task_id, expected):
                return False
            assert entity is not None
            updated_at = entity.question_gen_updated_at
            if updated_at is not None and updated_at >= threshold:
                return False
            entity.question_gen_status = target
            entity.question_gen_updated_at = self._now()
            return True

    @staticmethod
    def _matches(entity: Any, task_id: str, expected: str) -> bool:
        return (
            entity is not None
            and entity.question_gen_task_id == task_id
            and entity.question_gen_status == expected
        )

    @staticmethod
    def _read_config(value: str | None) -> QuestionGenerationConfig | None:
        if value is None or not value.strip():
            return None
        try:
            return QuestionGenerationConfig.model_validate_json(value)
        except ValueError as error:
            raise BusinessException(
                ErrorCode.INTERNAL_ERROR,
                "解析题目生成配置失败",
            ) from error

    @staticmethod
    def _response(
        entity: Any,
        config: QuestionGenerationConfig | None,
    ) -> QuestionGenStatusResponse:
        return QuestionGenStatusResponse(
            knowledge_base_id=entity.id,
            question_gen_status=QuestionGenStatus(entity.question_gen_status or "NONE"),
            question_gen_task_id=entity.question_gen_task_id,
            question_gen_config=config,
            saved_count=entity.question_gen_saved_count or 0,
            skipped_count=entity.question_gen_skipped_count or 0,
            message=entity.question_gen_message,
            error=entity.question_gen_error,
            updated_at=entity.question_gen_updated_at,
        )


class QuestionGenStreamProducer:
    def __init__(
        self,
        streams: RedisStreamService,
        state: QuestionGenerationStateService,
    ) -> None:
        self._streams = streams
        self._state = state

    async def send(
        self,
        knowledge_base_id: int,
        task_id: str,
        retry_count: int = 0,
    ) -> bool:
        try:
            await self._streams.add(
                KB_QUESTION_GEN.key,
                {
                    FIELD_KB_ID: str(knowledge_base_id),
                    FIELD_TASK_ID: task_id,
                    FIELD_RETRY_COUNT: str(retry_count),
                },
            )
            return True
        except Exception:
            logger.exception(
                "failed to enqueue question generation kbId=%s taskId=%s",
                knowledge_base_id,
                task_id,
            )
            await self._state.mark_failed(knowledge_base_id, task_id)
            return False


class KnowledgeBaseQuestionService:
    def __init__(
        self,
        session: AsyncSession,
        state: QuestionGenerationStateService,
        producer: QuestionGenStreamProducer,
        *,
        now: Callable[[], datetime] = datetime.now,
        user_id: uuid.UUID | None = None,
        default_provider_alias: str = "dashscope",
    ) -> None:
        self._session = session
        self._repository = KnowledgeBaseQuestionRepository(session, user_id)
        self._state = state
        self._producer = producer
        self._now = now
        self._default_provider_alias = default_provider_alias

    async def list_questions(
        self,
        knowledge_base_id: int,
        status: KnowledgeBaseQuestionStatus | None,
        category: str | None,
        difficulty: str | None,
        keyword: str | None,
    ) -> list[KnowledgeBaseQuestionDTO]:
        if await self._repository.knowledge_base(knowledge_base_id) is None:
            raise BusinessException(ErrorCode.KNOWLEDGE_BASE_NOT_FOUND)
        rows = await self._repository.list_questions(
            knowledge_base_id,
            status.value if status is not None else None,
        )
        category_filter = trim_to_none(category)
        difficulty_filter = trim_to_none(difficulty)
        keyword_filter = trim_to_none(keyword)
        return [
            question_dto(row)
            for row in rows
            if (category_filter is None or row.question.category == category_filter)
            and (difficulty_filter is None or row.question.difficulty == difficulty_filter)
            and (keyword_filter is None or self._contains_keyword(row.question, keyword_filter))
        ]

    async def list_categories(self, knowledge_base_id: int) -> list[CategoryCount]:
        if await self._repository.knowledge_base(knowledge_base_id) is None:
            raise BusinessException(ErrorCode.KNOWLEDGE_BASE_NOT_FOUND)
        return [
            CategoryCount(category=item.category, count=item.count)
            for item in await self._repository.categories(knowledge_base_id)
        ]

    async def create_question(
        self,
        knowledge_base_id: int,
        request: CreateKnowledgeBaseQuestionRequest,
    ) -> KnowledgeBaseQuestionDTO:
        knowledge_base = await self._repository.knowledge_base(knowledge_base_id)
        if knowledge_base is None:
            raise BusinessException(ErrorCode.KNOWLEDGE_BASE_NOT_FOUND)
        timestamp = self._now()
        entity = KnowledgeBaseQuestion(
            category=self._normalize_category(request.category, None),
            created_at=timestamp,
            difficulty=normalize_difficulty(request.difficulty),
            follow_ups_json=compact_json_text(sanitize_follow_ups(request.follow_ups)),
            kb_content_hash=knowledge_base.file_hash,
            key_points_json=compact_json_text(sanitized_strings(request.key_points)),
            knowledge_base_id=knowledge_base_id,
            question=request.question.strip(),
            reference_answer=trim_to_none(request.reference_answer),
            scoring_rubric=trim_to_none(request.scoring_rubric),
            skill_id=DEFAULT_SKILL_ID,
            source_context=trim_to_none(request.source_context),
            status=(request.status or KnowledgeBaseQuestionStatus.DRAFT).value,
            topic_summary=trim_to_none(request.topic_summary),
            type=trim_to_none(request.type),
            updated_at=timestamp,
        )
        await self._repository.add(entity)
        await self._session.commit()
        return question_dto(QuestionRow(entity, knowledge_base.name))

    async def update_question(
        self,
        question_id: int,
        request: UpdateKnowledgeBaseQuestionRequest,
    ) -> KnowledgeBaseQuestionDTO:
        row = await self._question_or_error(question_id)
        entity = row.question
        if request.difficulty is not None:
            entity.difficulty = normalize_difficulty(request.difficulty)
        if request.type is not None:
            entity.type = trim_to_none(request.type)
        if request.category is not None:
            if not request.category.strip():
                raise BusinessException(ErrorCode.BAD_REQUEST, "面试方向不能为空")
            entity.category = request.category.strip()
        if request.question is not None:
            if not request.question.strip():
                raise BusinessException(ErrorCode.BAD_REQUEST, "题干不能为空")
            entity.question = request.question.strip()
        if request.topic_summary is not None:
            entity.topic_summary = trim_to_none(request.topic_summary)
        if request.reference_answer is not None:
            entity.reference_answer = trim_to_none(request.reference_answer)
        if request.key_points is not None:
            entity.key_points_json = compact_json_text(sanitized_strings(request.key_points))
        if request.scoring_rubric is not None:
            entity.scoring_rubric = trim_to_none(request.scoring_rubric)
        if request.follow_ups is not None:
            entity.follow_ups_json = compact_json_text(sanitize_follow_ups(request.follow_ups))
        if request.source_context is not None:
            entity.source_context = trim_to_none(request.source_context)
        if request.status is not None:
            entity.status = request.status.value
        entity.updated_at = self._now()
        await self._session.commit()
        return question_dto(row)

    async def update_status(
        self,
        question_id: int,
        status: KnowledgeBaseQuestionStatus,
    ) -> KnowledgeBaseQuestionDTO:
        row = await self._question_or_error(question_id)
        row.question.status = status.value
        row.question.updated_at = self._now()
        await self._session.commit()
        return question_dto(row)

    async def delete_question(self, question_id: int) -> None:
        row = await self._repository.question(question_id)
        if row is None:
            raise BusinessException(ErrorCode.INTERVIEW_QUESTION_NOT_FOUND)
        await self._repository.delete_question(row.question)
        await self._session.commit()

    async def submit_generation_task(
        self,
        knowledge_base_id: int,
        request: GenerateKnowledgeBaseQuestionsRequest,
    ) -> QuestionGenStatusResponse:
        config = QuestionGenerationConfig(
            difficulty=normalize_difficulty(request.difficulty),
            question_count=max(1, request.question_count),
            follow_up_count=max(
                0,
                min(
                    request.follow_up_count
                    if request.follow_up_count is not None
                    else DEFAULT_FOLLOW_UP_COUNT,
                    MAX_FOLLOW_UP_COUNT,
                ),
            ),
            category_limit=max(
                1,
                min(request.category_limit or DEFAULT_CATEGORY_LIMIT, 5),
            ),
            llm_provider=trim_to_none(request.llm_provider) or self._default_provider_alias,
        )
        response = await self._state.create_task(knowledge_base_id, config)
        assert response.question_gen_task_id is not None
        sent = await self._producer.send(
            knowledge_base_id,
            response.question_gen_task_id,
        )
        return response if sent else await self._state.get_status(knowledge_base_id)

    async def generation_status(
        self,
        knowledge_base_id: int,
    ) -> QuestionGenStatusResponse:
        return await self._state.get_status(knowledge_base_id)

    async def _question_or_error(self, question_id: int) -> QuestionRow:
        row = await self._repository.question(question_id)
        if row is None:
            raise BusinessException(ErrorCode.INTERVIEW_QUESTION_NOT_FOUND)
        return row

    @staticmethod
    def _contains_keyword(entity: KnowledgeBaseQuestion, keyword: str) -> bool:
        lowered = keyword.lower()
        return any(
            value is not None and lowered in value.lower()
            for value in (
                entity.question,
                entity.reference_answer,
                entity.scoring_rubric,
                entity.topic_summary,
                entity.category,
            )
        )

    @staticmethod
    def _normalize_category(value: str | None, fallback: str | None) -> str:
        if value is None or not value.strip():
            return fallback.strip() if fallback is not None and fallback.strip() else "未分类"
        return value.strip()


class KnowledgeBaseQuestionGenerationService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        registry_factory: Callable[[uuid.UUID], ProviderRegistry],
        adapter: LlmAdapter,
        structured: StructuredOutputInvoker,
        prompts: PromptRepository,
        sanitizer: PromptSanitizer,
        state: QuestionGenerationStateService,
        *,
        context_retriever_factory: Callable[[uuid.UUID], QueryRetriever | None] | None = None,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._sessions = sessions
        self._registry_factory = registry_factory
        self._adapter = adapter
        self._structured = structured
        self._prompts = prompts
        self._sanitizer = sanitizer
        self._state = state
        self._context_retriever_factory = context_retriever_factory
        self._now = now

    async def execute(
        self,
        knowledge_base_id: int,
        task_id: str,
        config: QuestionGenerationConfig,
    ) -> None:
        async with self._sessions() as session:
            repository = KnowledgeBaseQuestionRepository(session)
            knowledge_base = await repository.knowledge_base(knowledge_base_id)
            if knowledge_base is None:
                raise BusinessException(ErrorCode.KNOWLEDGE_BASE_NOT_FOUND)
            if knowledge_base.question_gen_task_id != task_id:
                return
            knowledge_base_name = knowledge_base.name
            content_hash = knowledge_base.file_hash
            user_id = knowledge_base.user_id
            embedding_provider_alias = knowledge_base.embedding_provider_alias

        registry = self._registry_factory(user_id)
        difficulty = normalize_difficulty(config.difficulty)
        follow_up_count = max(0, min(config.follow_up_count, MAX_FOLLOW_UP_COUNT))
        category_limit = max(1, min(config.category_limit, 5))
        context = await self._generation_context(
            knowledge_base_id,
            user_id,
            embedding_provider_alias,
            registry,
        )
        generated = await self._call_llm(
            knowledge_base_id,
            knowledge_base_name,
            difficulty,
            max(1, config.question_count),
            follow_up_count,
            category_limit,
            config.llm_provider,
            context,
            registry,
        )
        if generated.questions is None or not generated.questions:
            raise BusinessException(
                ErrorCode.INTERVIEW_QUESTION_GENERATION_FAILED,
                "知识库题库生成结果为空",
            )
        questions, skipped_count = self._build_entities(
            knowledge_base_id,
            content_hash,
            knowledge_base_name,
            difficulty,
            context,
            follow_up_count,
            generated.questions,
        )
        if not questions:
            raise BusinessException(
                ErrorCode.INTERVIEW_QUESTION_GENERATION_FAILED,
                "知识库题库生成结果无有效题干",
            )
        await self._state.replace_questions_and_complete(
            knowledge_base_id,
            task_id,
            questions,
            skipped_count,
        )

    async def _generation_context(
        self,
        knowledge_base_id: int,
        user_id: uuid.UUID,
        provider_alias: str,
        registry: ProviderRegistry,
    ) -> str:
        query_repository = KnowledgeBaseQueryRepository(self._sessions, user_id)
        retriever = (
            self._context_retriever_factory(user_id)
            if self._context_retriever_factory is not None
            else None
        )
        provider = await registry.get_embedding(provider_alias) if retriever is None else None
        texts: list[str] = []
        seen: set[str] = set()
        for query in GENERATION_QUERIES:
            if retriever is not None:
                hits = await retriever.retrieve(
                    [knowledge_base_id],
                    query,
                    RETRIEVAL_QUERY_TOP_K,
                    0,
                )
            else:
                assert provider is not None
                embeddings = await self._adapter.embed(provider, [query])
                if not embeddings:
                    continue
                hits = await query_repository.similarity_search(
                    [knowledge_base_id],
                    embeddings[0],
                    RETRIEVAL_QUERY_TOP_K,
                    0,
                )
            for hit in hits:
                value = hit.content
                normalized = value.strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                texts.append(value)
                if len(texts) >= RETRIEVAL_TOP_K:
                    break
            if len(texts) >= RETRIEVAL_TOP_K:
                break
        if not texts:
            raise BusinessException(
                ErrorCode.KNOWLEDGE_BASE_QUERY_FAILED,
                "知识库未检索到可用于生成题目的内容",
            )
        context = "\n\n---\n\n".join(texts)
        if len(context) <= MAX_CONTEXT_CHARS:
            return context
        return context[:MAX_CONTEXT_CHARS] + "\n...(知识库片段过长，已截断)"

    async def _call_llm(
        self,
        knowledge_base_id: int,
        knowledge_base_name: str,
        difficulty: str,
        question_count: int,
        follow_up_count: int,
        category_limit: int,
        provider_id: str | None,
        context: str,
        registry: ProviderRegistry,
    ) -> GeneratedQuestionList:
        async with self._sessions() as session:
            repository = KnowledgeBaseQuestionRepository(session)
            categories = await repository.categories(knowledge_base_id)
            recent = await repository.recent_questions(
                knowledge_base_id,
                difficulty,
            )
        existing_categories = (
            "\n".join(f"- {item.category}（{item.count} 题）" for item in categories[:10])
            or "暂无已有方向"
        )
        existing_questions = (
            "\n".join(
                f"- {item.question.strip()}"
                for item in recent
                if item.question is not None and item.question.strip()
            )
            or "暂无已有题目"
        )
        provider = await registry.get_chat(
            None if provider_id in {None, "", "default"} else provider_id
        )
        effective_follow_up_count = (
            0 if isinstance(provider, OpenTrekProviderConfig) else follow_up_count
        )
        if isinstance(provider, OpenTrekProviderConfig) and question_count > 1:
            generated: list[GeneratedQuestion | None] = []
            keys: set[str] = set()
            attempts = 0
            max_attempts = question_count * 2
            batch_contexts = split_question_generation_context(context, question_count)
            while len(generated) < question_count and attempts < max_attempts:
                attempts += 1
                target_index = len(generated)
                previous = [
                    item.question.strip()
                    for item in generated
                    if item is not None and item.question is not None and item.question.strip()
                ]
                batch = await self._invoke_generation_batch(
                    provider,
                    knowledge_base_name,
                    difficulty,
                    1,
                    effective_follow_up_count,
                    category_limit,
                    existing_categories,
                    "\n".join((existing_questions, *(f"- {item}" for item in previous))),
                    batch_contexts[target_index],
                )
                candidate = next(
                    (
                        item
                        for item in batch.questions or []
                        if item is not None and item.question is not None and item.question.strip()
                    ),
                    None,
                )
                if candidate is None:
                    continue
                key = self._question_key(candidate.question or "")
                if key in keys:
                    continue
                keys.add(key)
                generated.append(candidate)
            if len(generated) < question_count:
                raise BusinessException(
                    ErrorCode.INTERVIEW_QUESTION_GENERATION_FAILED,
                    f"OpenTrek 仅生成 {len(generated)}/{question_count} 道不重复题目",
                )
            return GeneratedQuestionList(questions=generated)
        return await self._invoke_generation_batch(
            provider,
            knowledge_base_name,
            difficulty,
            question_count,
            effective_follow_up_count,
            category_limit,
            existing_categories,
            existing_questions,
            context,
        )

    async def _invoke_generation_batch(
        self,
        provider: ProviderConfig,
        knowledge_base_name: str,
        difficulty: str,
        question_count: int,
        follow_up_count: int,
        category_limit: int,
        existing_categories: str,
        existing_questions: str,
        context: str,
    ) -> GeneratedQuestionList:
        provider = opentrek_provider_for_kb_question_generation(provider)
        system = (
            self._prompts.render("knowledgebase-question-generation-system.st")
            + "\n\n"
            + QUESTION_OUTPUT_FORMAT
        )
        sanitized_context = cast(str, self._sanitizer.sanitize(context))
        user = self._prompts.render(
            "knowledgebase-question-generation-user.st",
            {
                "knowledgeBaseName": self._sanitizer.sanitize(knowledge_base_name),
                "difficulty": difficulty,
                "questionCount": question_count,
                "followUpCount": follow_up_count,
                "categoryLimit": category_limit,
                "existingCategories": self._sanitizer.sanitize(existing_categories),
                "existingQuestions": self._sanitizer.sanitize(existing_questions),
                "context": DATA_BOUNDARY_INSTRUCTION
                + "\n"
                + self._sanitizer.wrap_with_delimiters(
                    "knowledge-base",
                    sanitized_context,
                ),
            },
        )
        return await self._structured.invoke(
            provider,
            system,
            user,
            GeneratedQuestionList,
            ErrorCode.INTERVIEW_QUESTION_GENERATION_FAILED,
            "知识库题库生成失败：",
        )

    def _build_entities(
        self,
        knowledge_base_id: int,
        content_hash: str,
        knowledge_base_name: str,
        difficulty: str,
        context: str,
        follow_up_count: int,
        generated: Sequence[GeneratedQuestion | None],
    ) -> tuple[list[KnowledgeBaseQuestion], int]:
        timestamp = self._now()
        keys: set[str] = set()
        questions: list[KnowledgeBaseQuestion] = []
        skipped_count = 0
        for item in generated:
            if item is None or item.question is None or not item.question.strip():
                skipped_count += 1
                continue
            question = item.question.strip()
            key = self._question_key(question)
            if key in keys:
                skipped_count += 1
                continue
            keys.add(key)
            follow_ups = [
                KnowledgeBaseQuestionFollowUp(
                    question=follow_up.question,
                    reference_answer=follow_up.reference_answer,
                    key_points=follow_up.key_points,
                    scoring_rubric=follow_up.scoring_rubric,
                )
                for follow_up in item.follow_ups or ()
                if follow_up is not None
            ]
            questions.append(
                KnowledgeBaseQuestion(
                    category=(
                        item.category.strip()
                        if item.category is not None and item.category.strip()
                        else knowledge_base_name.strip()
                        if knowledge_base_name.strip()
                        else "未分类"
                    ),
                    created_at=timestamp,
                    difficulty=difficulty,
                    follow_ups_json=compact_json_text(
                        sanitize_follow_ups(
                            follow_ups,
                            limit=follow_up_count,
                        )
                    ),
                    kb_content_hash=content_hash,
                    key_points_json=compact_json_text(sanitized_strings(item.key_points)),
                    knowledge_base_id=knowledge_base_id,
                    question=question,
                    reference_answer=trim_to_none(item.reference_answer),
                    scoring_rubric=trim_to_none(item.scoring_rubric),
                    skill_id=DEFAULT_SKILL_ID,
                    source_context=context,
                    status=KnowledgeBaseQuestionStatus.DRAFT.value,
                    topic_summary=trim_to_none(item.topic_summary),
                    type=trim_to_none(item.type),
                    updated_at=timestamp,
                )
            )
        return questions, skipped_count

    @staticmethod
    def _question_key(value: str) -> str:
        normalized = unicodedata.normalize("NFC", value).lower()
        return "".join(character for character in normalized if character.isalnum())


def split_question_generation_context(context: str, question_count: int) -> list[str]:
    sections = [
        section.strip()
        for section in context.replace("\r\n", "\n").split("\n## ")
        if len(section.strip()) >= 80
    ]
    if len(sections) < question_count:
        return [context] * question_count
    return [sections[index] for index in range(question_count)]


class QuestionGenPayload:
    def __init__(self, knowledge_base_id: int, task_id: str) -> None:
        self.knowledge_base_id = knowledge_base_id
        self.task_id = task_id


class QuestionGenStreamHandler:
    def __init__(
        self,
        state: QuestionGenerationStateService,
        producer: QuestionGenStreamProducer,
        generation: KnowledgeBaseQuestionGenerationService,
    ) -> None:
        self._state = state
        self._producer = producer
        self._generation = generation

    async def parse(self, message: StreamMessage) -> QuestionGenPayload | None:
        knowledge_base_id = message.data.get(FIELD_KB_ID)
        task_id = message.data.get(FIELD_TASK_ID)
        if knowledge_base_id is None or task_id is None:
            return None
        return QuestionGenPayload(int(knowledge_base_id), task_id)

    async def should_skip(self, payload: QuestionGenPayload) -> bool:
        del payload
        return False

    async def try_mark_processing(self, payload: QuestionGenPayload) -> bool:
        return await self._state.try_mark_processing(
            payload.knowledge_base_id,
            payload.task_id,
        )

    async def process(self, payload: QuestionGenPayload) -> None:
        config = await self._state.get_config(
            payload.knowledge_base_id,
            payload.task_id,
        )
        await self._generation.execute(
            payload.knowledge_base_id,
            payload.task_id,
            config,
        )

    async def mark_completed(self, payload: QuestionGenPayload) -> None:
        del payload

    async def retry(self, payload: QuestionGenPayload, retry_count: int) -> None:
        if not await self._state.reset_for_retry(
            payload.knowledge_base_id,
            payload.task_id,
        ):
            return
        await self._producer.send(
            payload.knowledge_base_id,
            payload.task_id,
            retry_count,
        )

    async def mark_failed(self, payload: QuestionGenPayload, error: str) -> None:
        del error
        await self._state.mark_failed(
            payload.knowledge_base_id,
            payload.task_id,
        )


class RandomSelection(Protocol):
    def shuffle(self, values: list[Any]) -> None: ...

    def randrange(self, start: int, stop: int) -> int: ...


class SystemRandomSelection:
    def shuffle(self, values: list[Any]) -> None:
        random.shuffle(values)

    def randrange(self, start: int, stop: int) -> int:
        return random.randrange(start, stop)


class KnowledgeBaseInterviewService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        interview: InterviewService,
        *,
        random_selection: RandomSelection | None = None,
        user_id: uuid.UUID | None = None,
    ) -> None:
        self._sessions = sessions
        self._interview = interview
        self._random = random_selection or SystemRandomSelection()
        self._user_id = user_id

    async def create_session(
        self,
        request: CreateKnowledgeBaseInterviewRequest,
    ) -> InterviewSessionDTO:
        assert request.knowledge_base_id is not None
        category = trim_to_none(request.category)
        difficulty = normalize_difficulty(request.difficulty)
        async with self._sessions() as session:
            repository = KnowledgeBaseQuestionRepository(session, self._user_id)
            if await repository.knowledge_base(request.knowledge_base_id) is None:
                raise BusinessException(ErrorCode.KNOWLEDGE_BASE_NOT_FOUND)
            raw = await repository.active_questions(
                request.knowledge_base_id,
                difficulty,
                category,
            )
        if len(raw) < request.main_question_count:
            direction = category or "全部方向"
            raise BusinessException(
                ErrorCode.INTERVIEW_QUESTION_INSUFFICIENT,
                f"需要 {request.main_question_count} 道主问题，"
                f"但只有 {len(raw)} 道满足：方向={direction}、难度={difficulty}",
            )
        selected = list(raw)
        self._random.shuffle(selected)
        questions = self._build_interview_questions(selected[: request.main_question_count])
        return await self._interview.create_session_from_questions(
            questions,
            channel=InterviewChannel.KNOWLEDGE_BASE,
            max_follow_ups_per_main=request.follow_up_count,
            llm_provider=request.llm_provider,
            skill_id=DEFAULT_SKILL_ID,
            difficulty=difficulty,
            request_id=request.request_id,
            knowledge_base_id=request.knowledge_base_id,
            interview_category=category,
            context={"knowledgeBaseId": request.knowledge_base_id},
        )

    async def capacity(
        self,
        knowledge_base_id: int,
        category: str | None,
        difficulty: str,
        main_question_count: int,
    ) -> KnowledgeBaseInterviewCapacityResponse:
        normalized_category = trim_to_none(category)
        normalized_difficulty = normalize_difficulty(difficulty)
        async with self._sessions() as session:
            repository = KnowledgeBaseQuestionRepository(session, self._user_id)
            if await repository.knowledge_base(knowledge_base_id) is None:
                raise BusinessException(ErrorCode.KNOWLEDGE_BASE_NOT_FOUND)
            raw = await repository.active_questions(
                knowledge_base_id,
                normalized_difficulty,
                None,
            )
        scoped = [
            question
            for question in raw
            if normalized_category is None or question.category == normalized_category
        ]
        counts: dict[str, int] = {}
        for question in raw:
            category_value = trim_to_none(question.category)
            if category_value is not None:
                counts[category_value] = counts.get(category_value, 0) + 1
        categories = [
            InterviewCategoryCapacity(
                category=category_value,
                available_question_count=count,
            )
            for category_value, count in sorted(
                counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        options = []
        for count in range(0, MAX_FOLLOW_UP_COUNT + 1):
            available = len(scoped)
            options.append(
                InterviewFollowUpCapacity(
                    follow_up_count=count,
                    available_question_count=available,
                    selectable=main_question_count > 0 and available >= main_question_count,
                )
            )
        return KnowledgeBaseInterviewCapacityResponse(
            knowledge_base_id=knowledge_base_id,
            category=normalized_category,
            difficulty=normalized_difficulty,
            main_question_count=main_question_count,
            categories=categories,
            follow_up_options=options,
            reference_answer_coverage=sum(bool(item.reference_answer) for item in scoped),
            key_points_coverage=sum(bool(item.key_points_json) for item in scoped),
            scoring_rubric_coverage=sum(bool(item.scoring_rubric) for item in scoped),
        )

    def _build_interview_questions(
        self,
        selected: Sequence[KnowledgeBaseQuestion],
    ) -> list[PlannedInterviewQuestion]:
        result: list[PlannedInterviewQuestion] = []
        for entity in selected:
            candidate_follow_ups = self._usable_follow_ups(entity.follow_ups_json)
            source_context = entity.source_context or ""
            if candidate_follow_ups:
                source_context = (
                    source_context
                    + "\n\n候选追问素材："
                    + compact_json_text(
                        [item.model_dump(by_alias=True) for item in candidate_follow_ups]
                    )
                )
            result.append(
                PlannedInterviewQuestion(
                    question=entity.question,
                    type=entity.type or "KNOWLEDGE_BASE",
                    category=entity.category or "知识库",
                    topic_summary=entity.topic_summary,
                    reference_answer=entity.reference_answer,
                    key_points=parse_string_list(entity.key_points_json),
                    scoring_rubric=entity.scoring_rubric,
                    source_context=source_context or None,
                    source_question_id=entity.id,
                )
            )
        return result

    def _pick_follow_ups(
        self,
        pool: list[KnowledgeBaseQuestionFollowUp],
        count: int,
    ) -> list[KnowledgeBaseQuestionFollowUp]:
        if count <= 0:
            return []
        if len(pool) < count:
            raise BusinessException(
                ErrorCode.INTERVIEW_QUESTION_INSUFFICIENT,
                f"追问池在组装面试时发生变化，无法严格抽取 {count} 个追问",
            )
        if len(pool) == count:
            return list(pool)
        values = list(pool)
        for index in range(count):
            selected = self._random.randrange(index, len(values))
            values[index], values[selected] = values[selected], values[index]
        return values[:count]

    @staticmethod
    def _usable_follow_ups(
        value: str | None,
    ) -> list[KnowledgeBaseQuestionFollowUp]:
        return [
            follow_up.model_copy(update={"question": follow_up.question.strip()})
            for follow_up in parse_follow_ups(value)
            if follow_up.question is not None and follow_up.question.strip()
        ]


class QuestionGenerationRecoveryService:
    def __init__(
        self,
        state: QuestionGenerationStateService,
        producer: QuestionGenStreamProducer,
        *,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._state = state
        self._producer = producer
        self._now = now

    async def recover(self) -> None:
        now = self._now()
        queued_threshold = now - timedelta(minutes=2)
        processing_threshold = now - timedelta(minutes=20)
        for knowledge_base_id, task_id in await self._state.stale_tasks(
            QuestionGenStatus.QUEUED,
            queued_threshold,
        ):
            if task_id is not None and await self._state.touch_queued_for_recovery(
                knowledge_base_id,
                task_id,
                queued_threshold,
            ):
                await self._producer.send(knowledge_base_id, task_id)
        for knowledge_base_id, task_id in await self._state.stale_tasks(
            QuestionGenStatus.PROCESSING,
            processing_threshold,
        ):
            if task_id is not None and await self._state.reset_stale_processing(
                knowledge_base_id,
                task_id,
                processing_threshold,
            ):
                await self._producer.send(knowledge_base_id, task_id)
