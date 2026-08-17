from __future__ import annotations

import os
import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, cast
from urllib.parse import urlsplit

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, select

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.prompts import PromptRepository, PromptSanitizer
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import (
    InterviewAnswer,
    InterviewSession,
    KnowledgeBase,
    KnowledgeBaseQuestion,
    VectorStore,
)
from interview_guide.common.db.session import Database
from interview_guide.common.errors import BusinessException
from interview_guide.common.redis.streams import (
    INTERVIEW_EVALUATE,
    KB_QUESTION_GEN,
    RedisStreamService,
    SequentialStreamConsumer,
)
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.modules.interview.cache import InterviewSessionCache
from interview_guide.modules.interview.repository import InterviewRepository
from interview_guide.modules.interview.service import InterviewService
from interview_guide.modules.knowledge_base.question_models import (
    CreateKnowledgeBaseInterviewRequest,
    CreateKnowledgeBaseQuestionRequest,
    GeneratedQuestion,
    GeneratedQuestionFollowUp,
    GeneratedQuestionList,
    GenerateKnowledgeBaseQuestionsRequest,
    KnowledgeBaseQuestionStatus,
    UpdateKnowledgeBaseQuestionRequest,
)
from interview_guide.modules.knowledge_base.question_service import (
    KnowledgeBaseInterviewService,
    KnowledgeBaseQuestionGenerationService,
    KnowledgeBaseQuestionService,
    QuestionGenerationRecoveryService,
    QuestionGenerationStateService,
    QuestionGenStreamHandler,
    QuestionGenStreamProducer,
)
from interview_guide.modules.knowledge_base.vectorization import EMBEDDING_DIMENSIONS

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
REDIS_URL = os.getenv("TEST_REDIS_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        POSTGRES_URL is None or REDIS_URL is None,
        reason="TEST_POSTGRES_URL and TEST_REDIS_URL are required",
    ),
]
FIXED_NOW = datetime(2026, 8, 17, 8, 0)
TASK_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
CHAT_PROVIDER = ProviderConfig(
    provider_id="explicit-fake-chat",
    base_url="http://127.0.0.1",
    api_key="explicit-fake",
    model="explicit-fake-chat",
)
EMBEDDING_PROVIDER = ProviderConfig(
    provider_id="explicit-fake-embedding",
    base_url="http://127.0.0.1",
    api_key="explicit-fake",
    model="explicit-fake-chat",
    embedding_model="explicit-fake-embedding",
    embedding_dimensions=EMBEDDING_DIMENSIONS,
    supports_embedding=True,
)


def integration_settings() -> Settings:
    assert POSTGRES_URL is not None
    assert REDIS_URL is not None
    postgres = urlsplit(POSTGRES_URL)
    redis = urlsplit(REDIS_URL)
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="knowledge-question-integration-key",
        POSTGRES_HOST=postgres.hostname or "127.0.0.1",
        POSTGRES_PORT=postgres.port or 5432,
        POSTGRES_DB=postgres.path.removeprefix("/"),
        POSTGRES_USER=postgres.username or "postgres",
        POSTGRES_PASSWORD=postgres.password or "",
        REDIS_HOST=redis.hostname or "127.0.0.1",
        REDIS_PORT=redis.port or 6379,
        REDIS_DB=int(redis.path.removeprefix("/") or "0"),
    )


async def cleanup(database: Database, redis: Redis) -> None:
    async with database.sessions() as session, session.begin():
        session_ids = select(InterviewSession.id).where(
            InterviewSession.knowledge_base_id.in_(
                select(KnowledgeBase.id).where(
                    KnowledgeBase.file_hash.like("knowledge-question-integration-%")
                )
            )
        )
        await session.execute(
            delete(InterviewAnswer).where(InterviewAnswer.session_id.in_(session_ids))
        )
        await session.execute(delete(InterviewSession).where(InterviewSession.id.in_(session_ids)))
        knowledge_base_ids = select(KnowledgeBase.id).where(
            KnowledgeBase.file_hash.like("knowledge-question-integration-%")
        )
        await session.execute(
            delete(KnowledgeBaseQuestion).where(
                KnowledgeBaseQuestion.knowledge_base_id.in_(knowledge_base_ids)
            )
        )
        await session.execute(
            delete(VectorStore).where(
                VectorStore.metadata_json["integration_test"].astext == "question-bank"
            )
        )
        await session.execute(
            delete(KnowledgeBase).where(
                KnowledgeBase.file_hash.like("knowledge-question-integration-%")
            )
        )
    keys = [
        key
        async for key in redis.scan_iter(
            match="interview:*",
        )
    ]
    if keys:
        await redis.delete(*keys)
    await redis.delete(KB_QUESTION_GEN.key)


async def seed_knowledge_base(
    database: Database,
    suffix: str,
    *,
    question_status: str = "NONE",
    task_id: str | None = None,
    updated_at: datetime | None = None,
) -> int:
    async with database.sessions() as session, session.begin():
        entity = KnowledgeBase(
            access_count=1,
            category="集成测试",
            chunk_count=1,
            content_type="text/plain",
            file_hash=f"knowledge-question-integration-{suffix}",
            file_size=100,
            last_accessed_at=FIXED_NOW,
            name=f"题库集成测试-{suffix}",
            original_filename=f"{suffix}.txt",
            question_count=0,
            question_gen_status=question_status,
            question_gen_error=None,
            question_gen_task_id=task_id,
            question_gen_config=None,
            question_gen_message=None,
            question_gen_saved_count=0,
            question_gen_skipped_count=0,
            question_gen_updated_at=updated_at,
            storage_key=None,
            storage_url=None,
            uploaded_at=FIXED_NOW,
            vector_error=None,
            vector_status="COMPLETED",
        )
        session.add(entity)
        await session.flush()
        return entity.id


def fixed_embedding() -> list[float]:
    return [1.0, 0.0] + [0.0] * (EMBEDDING_DIMENSIONS - 2)


class ExplicitFakeRegistry:
    async def get_chat(self, provider_id: str | None = None) -> ProviderConfig:
        del provider_id
        return CHAT_PROVIDER

    async def get_embedding(
        self,
        provider_id: str | None = None,
    ) -> ProviderConfig:
        del provider_id
        return EMBEDDING_PROVIDER


class ExplicitFakeAdapter:
    def __init__(self) -> None:
        self.embedding_inputs: list[list[str]] = []

    async def embed(
        self,
        provider: ProviderConfig,
        inputs: Sequence[str],
    ) -> list[list[float]]:
        assert provider is EMBEDDING_PROVIDER
        self.embedding_inputs.append(list(inputs))
        return [fixed_embedding() for _ in inputs]


class ExplicitFakeStructured:
    def __init__(self) -> None:
        self.system_prompt = ""
        self.user_prompt = ""

    async def invoke(
        self,
        provider: ProviderConfig,
        system_prompt_with_format: str,
        user_prompt: str,
        output_type: type[Any],
        error_code: object,
        error_prefix: str,
        **kwargs: object,
    ) -> GeneratedQuestionList:
        del output_type, error_code, error_prefix, kwargs
        assert provider is CHAT_PROVIDER
        self.system_prompt = system_prompt_with_format
        self.user_prompt = user_prompt
        follow_ups = [
            GeneratedQuestionFollowUp(
                question="追问一",
                referenceAnswer="追问答案一",
                keyPoints=["追问要点一"],
                scoringRubric="追问规则一",
            ),
            GeneratedQuestionFollowUp(
                question="追问二",
                referenceAnswer="追问答案二",
                keyPoints=["追问要点二"],
                scoringRubric="追问规则二",
            ),
            GeneratedQuestionFollowUp(
                question="追问三",
                referenceAnswer="追问答案三",
                keyPoints=["追问要点三"],
                scoringRubric="追问规则三",
            ),
        ]
        return GeneratedQuestionList(
            questions=[
                GeneratedQuestion(
                    category="Redis",
                    type="REDIS",
                    question="什么是 Redis 持久化？",
                    topicSummary="Redis 持久化",
                    referenceAnswer="RDB 与 AOF",
                    keyPoints=["RDB", "AOF"],
                    scoringRubric="10 分制",
                    followUps=follow_ups,
                ),
                GeneratedQuestion(
                    category="Redis",
                    type="REDIS",
                    question="什么是Redis持久化",
                    topicSummary="重复题",
                    referenceAnswer="重复",
                    keyPoints=[],
                    scoringRubric="重复",
                    followUps=[],
                ),
                GeneratedQuestion(
                    category="事务",
                    type=None,
                    question="如何理解事务边界？",
                    topicSummary="事务边界",
                    referenceAnswer="最小事务",
                    keyPoints=["一致性"],
                    scoringRubric="10 分制",
                    followUps=follow_ups[:1],
                ),
            ]
        )


class ExplicitFailingGeneration:
    async def execute(
        self,
        knowledge_base_id: int,
        task_id: str,
        config: object,
    ) -> None:
        del knowledge_base_id, task_id, config
        raise RuntimeError("explicit fake provider failure")


class NoShuffleRandom:
    def shuffle(self, values: list[Any]) -> None:
        del values

    def randrange(self, start: int, stop: int) -> int:
        del stop
        return start


@pytest.mark.asyncio
async def test_explicit_fake_generation_uses_real_pgvector_redis_retry_ack_and_snapshot() -> None:
    assert REDIS_URL is not None
    database = Database(integration_settings())
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    streams = RedisStreamService(redis)
    await cleanup(database, redis)
    knowledge_base_id = await seed_knowledge_base(database, "generation")
    async with database.sessions() as session, session.begin():
        session.add(
            VectorStore(
                content="Redis 支持 RDB 与 AOF，事务边界应尽量缩小。",
                metadata_json={
                    "kb_id": str(knowledge_base_id),
                    "integration_test": "question-bank",
                },
                embedding=fixed_embedding(),
            )
        )
    state = QuestionGenerationStateService(
        database.sessions,
        now=lambda: FIXED_NOW,
        task_id_factory=lambda: TASK_ID,
    )
    producer = QuestionGenStreamProducer(streams, state)
    try:
        async with database.sessions() as session:
            service = KnowledgeBaseQuestionService(
                session,
                state,
                producer,
                now=lambda: FIXED_NOW,
            )
            queued = await service.submit_generation_task(
                knowledge_base_id,
                GenerateKnowledgeBaseQuestionsRequest(
                    difficulty="mid",
                    questionCount=3,
                    followUpCount=2,
                    categoryLimit=3,
                    llmProvider=None,
                ),
            )
        assert queued.question_gen_status == "QUEUED"
        assert queued.question_gen_task_id == TASK_ID
        assert queued.question_gen_config is not None
        assert queued.question_gen_config.model_dump(by_alias=True) == {
            "difficulty": "mid",
            "questionCount": 3,
            "followUpCount": 2,
            "categoryLimit": 3,
            "llmProvider": None,
        }

        await streams.ensure_group(KB_QUESTION_GEN)
        first = (
            await streams.read_batch(
                KB_QUESTION_GEN,
                "question-gen-consumer-integration",
                block_ms=10,
                pending_idle_ms=60_000,
            )
        )[0]
        failing_consumer = SequentialStreamConsumer(
            streams,
            KB_QUESTION_GEN,
            "question-gen-consumer-integration",
            QuestionGenStreamHandler(
                state,
                producer,
                cast(Any, ExplicitFailingGeneration()),
            ),
        )
        await failing_consumer.process_message(first)
        retry_status = await state.get_status(knowledge_base_id)
        assert retry_status.question_gen_status == "QUEUED"
        pending = await redis.xpending(KB_QUESTION_GEN.key, KB_QUESTION_GEN.group)
        assert pending["pending"] == 0
        messages = await redis.xrange(KB_QUESTION_GEN.key)
        assert messages[-1][1] == {
            "kbId": str(knowledge_base_id),
            "taskId": TASK_ID,
            "retryCount": "1",
        }

        adapter = ExplicitFakeAdapter()
        structured = ExplicitFakeStructured()
        generation = KnowledgeBaseQuestionGenerationService(
            database.sessions,
            cast(Any, ExplicitFakeRegistry()),
            cast(Any, adapter),
            cast(Any, structured),
            PromptRepository(
                __import__("pathlib").Path(__file__).resolve().parents[2] / "resources"
            ),
            PromptSanitizer(uuid_factory=lambda: uuid.UUID(int=0)),
            state,
            now=lambda: FIXED_NOW,
        )
        retry_message = (
            await streams.read_batch(
                KB_QUESTION_GEN,
                "question-gen-consumer-integration",
                block_ms=10,
                pending_idle_ms=60_000,
            )
        )[0]
        successful_consumer = SequentialStreamConsumer(
            streams,
            KB_QUESTION_GEN,
            "question-gen-consumer-integration",
            QuestionGenStreamHandler(state, producer, generation),
        )
        await successful_consumer.process_message(retry_message)

        completed = await state.get_status(knowledge_base_id)
        assert completed.question_gen_status == "COMPLETED"
        assert completed.saved_count == 2
        assert completed.skipped_count == 1
        assert completed.message == "已生成 2 道题，跳过 1 道重复题"
        assert completed.error is None
        assert len(adapter.embedding_inputs) == 4
        assert "# Existing Categories" in structured.user_prompt
        assert "data-boundary-00000000-knowledge-base" in structured.user_prompt
        async with database.sessions() as verification:
            questions = list(
                await verification.scalars(
                    select(KnowledgeBaseQuestion)
                    .where(KnowledgeBaseQuestion.knowledge_base_id == knowledge_base_id)
                    .order_by(KnowledgeBaseQuestion.id)
                )
            )
        assert [question.status for question in questions] == ["DRAFT", "DRAFT"]
        assert len(__import__("json").loads(questions[0].follow_ups_json or "[]")) == 2
        assert len(__import__("json").loads(questions[1].follow_ups_json or "[]")) == 1
        pending = await redis.xpending(KB_QUESTION_GEN.key, KB_QUESTION_GEN.group)
        assert pending["pending"] == 0
    finally:
        await cleanup(database, redis)
        await redis.aclose()
        await database.close()


@pytest.mark.asyncio
async def test_real_postgres_redis_question_crud_capacity_and_specialized_session() -> None:
    assert REDIS_URL is not None
    database = Database(integration_settings())
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    streams = RedisStreamService(redis)
    blocking = BlockingExecutor(1)
    await cleanup(database, redis)
    knowledge_base_id = await seed_knowledge_base(database, "crud")
    state = QuestionGenerationStateService(database.sessions, now=lambda: FIXED_NOW)
    producer = QuestionGenStreamProducer(streams, state)
    try:
        async with database.sessions() as session:
            questions = KnowledgeBaseQuestionService(
                session,
                state,
                producer,
                now=lambda: FIXED_NOW,
            )
            first = await questions.create_question(
                knowledge_base_id,
                CreateKnowledgeBaseQuestionRequest(
                    difficulty="mid",
                    type="REDIS",
                    category="Redis",
                    question="Redis 主问题",
                    referenceAnswer="固定答案",
                    keyPoints=[" 要点一 "],
                    followUps=[
                        {
                            "question": "Redis 追问一",
                            "referenceAnswer": "追问答案一",
                            "keyPoints": ["追问要点一"],
                            "scoringRubric": "追问规则一",
                        },
                        {
                            "question": "Redis 追问二",
                            "referenceAnswer": "追问答案二",
                            "keyPoints": ["追问要点二"],
                            "scoringRubric": "追问规则二",
                        },
                    ],
                    status="ACTIVE",
                ),
            )
            second = await questions.create_question(
                knowledge_base_id,
                CreateKnowledgeBaseQuestionRequest(
                    difficulty="mid",
                    type="MYSQL",
                    category="MySQL",
                    question="MySQL 主问题",
                    followUps=[
                        {"question": "MySQL 追问一"},
                    ],
                    status="ACTIVE",
                ),
            )
            archived = await questions.create_question(
                knowledge_base_id,
                CreateKnowledgeBaseQuestionRequest(
                    difficulty="senior",
                    category="Redis",
                    question="待归档问题",
                ),
            )
            filtered = await questions.list_questions(
                knowledge_base_id,
                KnowledgeBaseQuestionStatus.ACTIVE,
                "Redis",
                "mid",
                "固定答案",
            )
            assert [item.id for item in filtered] == [first.id]
            assert filtered[0].key_points == ["要点一"]
            assert [
                (item.category, item.count)
                for item in await questions.list_categories(knowledge_base_id)
            ] == [("Redis", 2), ("MySQL", 1)]
            updated = await questions.update_question(
                archived.id,
                UpdateKnowledgeBaseQuestionRequest(
                    category="事务",
                    question="事务主问题",
                    difficulty="mid",
                    followUps=[{"question": "事务追问一"}],
                ),
            )
            assert updated.category == "事务"
            await questions.update_status(
                archived.id,
                KnowledgeBaseQuestionStatus.ACTIVE,
            )
            await questions.delete_question(second.id)

        repository = InterviewRepository(
            database.sessions,
            now=lambda: FIXED_NOW,
        )
        interview = InterviewService(
            repository,
            InterviewSessionCache(redis),
            streams,
            cast(Any, None),
            cast(Any, None),
            cast(Any, None),
            blocking,
            uuid_factory=lambda: uuid.UUID("11111111-1111-1111-1111-111111111111"),
        )
        specialized = KnowledgeBaseInterviewService(
            database.sessions,
            interview,
            random_selection=NoShuffleRandom(),
        )
        capacity = await specialized.capacity(
            knowledge_base_id,
            None,
            "mid",
            2,
        )
        assert [
            (
                item.category,
                item.available_question_count,
            )
            for item in capacity.categories
        ] == [("Redis", 1), ("事务", 1)]
        assert [
            (
                item.follow_up_count,
                item.available_question_count,
                item.selectable,
            )
            for item in capacity.follow_up_options[:3]
        ] == [(0, 2, True), (1, 2, True), (2, 1, False)]
        with pytest.raises(BusinessException, match="每题至少 2 个追问"):
            await specialized.create_session(
                CreateKnowledgeBaseInterviewRequest(
                    knowledgeBaseId=knowledge_base_id,
                    category=None,
                    difficulty="mid",
                    mainQuestionCount=2,
                    followUpCount=2,
                )
            )

        created = await specialized.create_session(
            CreateKnowledgeBaseInterviewRequest(
                knowledgeBaseId=knowledge_base_id,
                category=None,
                difficulty="mid",
                mainQuestionCount=2,
                followUpCount=1,
                llmProvider="",
            )
        )
        assert created.session_id == "1111111111111111"
        assert created.knowledge_base_id == knowledge_base_id
        assert created.interview_category is None
        assert created.total_questions == 4
        assert [item.question_index for item in created.questions] == [0, 1, 2, 3]
        assert [item.parent_question_index for item in created.questions] == [
            None,
            0,
            None,
            2,
        ]
        async with database.sessions() as verification:
            entity = await verification.scalar(
                select(InterviewSession).where(InterviewSession.session_id == created.session_id)
            )
        assert entity is not None
        assert entity.source_type == "KNOWLEDGE_BASE"
        assert entity.skill_id == "knowledge-base"
        assert entity.knowledge_base_id == knowledge_base_id

        await redis.delete(INTERVIEW_EVALUATE.key)
        for question in created.questions:
            await interview.submit_answer(
                created.session_id,
                question.question_index,
                f"固定答案-{question.question_index}",
            )
        evaluation_messages = await redis.xrange(INTERVIEW_EVALUATE.key)
        assert evaluation_messages[-1][1] == {
            "sessionId": created.session_id,
            "retryCount": "0",
        }
        stored = await repository.find_session(created.session_id)
        assert stored is not None
        assert stored.session.evaluate_status == "PENDING"
    finally:
        await cleanup(database, redis)
        await blocking.shutdown()
        await redis.aclose()
        await database.close()


@pytest.mark.asyncio
async def test_real_postgres_redis_scheduler_recovers_stale_generation_tasks() -> None:
    assert REDIS_URL is not None
    database = Database(integration_settings())
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    streams = RedisStreamService(redis)
    await cleanup(database, redis)
    queued_id = await seed_knowledge_base(
        database,
        "stale-queued",
        question_status="QUEUED",
        task_id="queued-task",
        updated_at=FIXED_NOW - timedelta(minutes=3),
    )
    processing_id = await seed_knowledge_base(
        database,
        "stale-processing",
        question_status="PROCESSING",
        task_id="processing-task",
        updated_at=FIXED_NOW - timedelta(minutes=21),
    )
    state = QuestionGenerationStateService(database.sessions, now=lambda: FIXED_NOW)
    recovery = QuestionGenerationRecoveryService(
        state,
        QuestionGenStreamProducer(streams, state),
        now=lambda: FIXED_NOW,
    )
    try:
        await recovery.recover()
        messages = [fields for _, fields in await redis.xrange(KB_QUESTION_GEN.key)]
        assert messages == [
            {
                "kbId": str(queued_id),
                "taskId": "queued-task",
                "retryCount": "0",
            },
            {
                "kbId": str(processing_id),
                "taskId": "processing-task",
                "retryCount": "0",
            },
        ]
        assert (await state.get_status(queued_id)).question_gen_status == "QUEUED"
        assert (await state.get_status(processing_id)).question_gen_status == "QUEUED"
    finally:
        await cleanup(database, redis)
        await redis.aclose()
        await database.close()
