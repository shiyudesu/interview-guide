from __future__ import annotations

import os
import uuid
from io import BytesIO
from urllib.parse import urlsplit

import pytest
from pdfminer.high_level import extract_text
from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import (
    InterviewAnswer,
    InterviewSession,
    Resume,
)
from interview_guide.common.db.session import Database
from interview_guide.common.errors import BusinessException
from interview_guide.common.redis.streams import (
    INTERVIEW_EVALUATE,
    RedisStreamService,
    SequentialStreamConsumer,
)
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.modules.interview.cache import (
    CREATE_RESULT_PREFIX,
    RESUME_SESSION_KEY_PREFIX,
    SESSION_KEY_PREFIX,
    InterviewSessionCache,
)
from interview_guide.modules.interview.models import (
    CategoryScore,
    CreateInterviewRequest,
    InterviewQuestion,
    InterviewReportDTO,
    QuestionEvaluation,
    ReferenceAnswer,
)
from interview_guide.modules.interview.repository import InterviewRepository
from interview_guide.modules.interview.service import (
    InterviewEvaluateHandler,
    InterviewService,
)

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
REDIS_URL = os.getenv("TEST_REDIS_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        POSTGRES_URL is None or REDIS_URL is None,
        reason="TEST_POSTGRES_URL and TEST_REDIS_URL are required",
    ),
]
FIXED_NOW = __import__("datetime").datetime(2026, 8, 16, 8, 0)
PROVIDER = ProviderConfig(
    provider_id="explicit-fake",
    base_url="http://127.0.0.1",
    api_key="explicit-fake",
    model="explicit-fake",
)


def integration_settings() -> Settings:
    assert POSTGRES_URL is not None
    assert REDIS_URL is not None
    postgres = urlsplit(POSTGRES_URL)
    redis = urlsplit(REDIS_URL)
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="interview-integration-key",
        POSTGRES_HOST=postgres.hostname or "127.0.0.1",
        POSTGRES_PORT=postgres.port or 5432,
        POSTGRES_DB=postgres.path.removeprefix("/"),
        POSTGRES_USER=postgres.username or "postgres",
        POSTGRES_PASSWORD=postgres.password or "",
        REDIS_HOST=redis.hostname or "127.0.0.1",
        REDIS_PORT=redis.port or 6379,
        REDIS_DB=int(redis.path.removeprefix("/") or "0"),
    )


class ExplicitFakeQuestionService:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, **values: object) -> list[InterviewQuestion]:
        del values
        self.calls += 1
        return [
            InterviewQuestion(
                question_index=0,
                question="什么是事务？",
                type="DATABASE",
                category="数据库",
            ),
            InterviewQuestion(
                question_index=1,
                question="如何排查慢查询？",
                type="DATABASE",
                category="数据库",
            ),
        ]


class ExplicitFakeRegistry:
    async def get_chat(self, provider_id: str | None = None) -> ProviderConfig:
        del provider_id
        return PROVIDER


class ExplicitFakeEvaluationService:
    def __init__(self) -> None:
        self.calls = 0

    async def evaluate(
        self,
        provider: ProviderConfig,
        session_id: str,
        resume_text: str,
        questions: list[InterviewQuestion],
        skill_id: str | None,
    ) -> InterviewReportDTO:
        del provider, resume_text, skill_id
        self.calls += 1
        return InterviewReportDTO(
            session_id=session_id,
            total_questions=len(questions),
            overall_score=40,
            category_scores=[
                CategoryScore(
                    category="数据库",
                    score=40,
                    question_count=len(questions),
                )
            ],
            question_details=[
                QuestionEvaluation(
                    question_index=item.question_index,
                    question=item.question,
                    category=item.category,
                    user_answer=item.user_answer,
                    score=80 if item.user_answer else 0,
                    feedback="固定 fake 反馈" if item.user_answer else "未回答",
                )
                for item in questions
            ],
            overall_feedback="固定 fake 总评",
            strengths=["事务基础"],
            improvements=["慢查询分析"],
            reference_answers=[
                ReferenceAnswer(
                    question_index=item.question_index,
                    question=item.question,
                    reference_answer="固定参考答案",
                    key_points=["固定要点"],
                )
                for item in questions
            ],
        )


async def cleanup(database: Database, redis: Redis) -> None:
    async with database.sessions() as session, session.begin():
        session_ids = select(InterviewSession.id).where(
            InterviewSession.request_id.like("interview-integration-%")
        )
        await session.execute(
            delete(InterviewAnswer).where(InterviewAnswer.session_id.in_(session_ids))
        )
        await session.execute(
            delete(InterviewSession).where(
                InterviewSession.request_id.like("interview-integration-%")
            )
        )
        await session.execute(
            delete(Resume).where(Resume.file_hash.like("interview-integration-%"))
        )
    keys = [
        key
        async for key in redis.scan_iter(
            match="interview:*",
        )
    ]
    if keys:
        await redis.delete(*keys)


async def seed_resume(database: Database) -> int:
    async with database.sessions() as session, session.begin():
        entity = Resume(
            access_count=1,
            analyze_error=None,
            analyze_status="COMPLETED",
            content_type="text/plain",
            file_hash="interview-integration-resume",
            file_size=20,
            last_accessed_at=FIXED_NOW,
            original_filename="interview-integration.txt",
            resume_text="固定简历内容",
            storage_key=None,
            storage_url=None,
            uploaded_at=FIXED_NOW,
        )
        session.add(entity)
        await session.flush()
        return entity.id


@pytest.mark.asyncio
async def test_real_postgres_redis_interview_crud_idempotency_and_pdf() -> None:
    assert REDIS_URL is not None
    database = Database(integration_settings())
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    blocking = BlockingExecutor(2)
    await cleanup(database, redis)
    resume_id = await seed_resume(database)
    questions = ExplicitFakeQuestionService()
    evaluation = ExplicitFakeEvaluationService()
    uuids = iter(
        (
            uuid.UUID("11111111-1111-1111-1111-111111111111"),
            uuid.UUID("22222222-2222-2222-2222-222222222222"),
        )
    )
    repository = InterviewRepository(database.sessions, now=lambda: FIXED_NOW)
    service = InterviewService(
        repository,
        InterviewSessionCache(redis),
        RedisStreamService(redis),
        questions,  # type: ignore[arg-type]
        evaluation,  # type: ignore[arg-type]
        ExplicitFakeRegistry(),  # type: ignore[arg-type]
        blocking,
        uuid_factory=lambda: next(uuids),
    )
    request_id = "interview-integration-request"
    request = CreateInterviewRequest(
        resumeText="固定简历内容",
        resumeId=resume_id,
        questionCount=3,
        skillId="java-backend",
        difficulty="mid",
        requestId=request_id,
    )

    try:
        with pytest.raises(BusinessException, match="requestId 格式不正确"):
            await service.create_session(request.model_copy(update={"request_id": "bad"}))

        created = await service.create_session(request)
        assert created.session_id == "1111111111111111"
        assert created.total_questions == 2
        assert questions.calls == 1
        assert (await service.find_unfinished_or_throw(resume_id)).session_id == created.session_id

        duplicate = await service.create_session(request)
        assert duplicate.session_id == created.session_id
        assert questions.calls == 1
        with pytest.raises(IntegrityError):
            await repository.create_session(
                session_id="9999999999999999",
                resume_id=None,
                questions=created.questions,
                llm_provider="default",
                skill_id="java-backend",
                difficulty="mid",
                request_id=request_id,
            )
        result_key = f"{CREATE_RESULT_PREFIX}{request_id}"
        assert await redis.get(result_key) == created.session_id
        assert 86_390 <= await redis.ttl(result_key) <= 86_400
        session_key = f"{SESSION_KEY_PREFIX}{created.session_id}"
        assert 86_390 <= await redis.ttl(session_key) <= 86_400
        assert await redis.get(f"{RESUME_SESSION_KEY_PREFIX}{resume_id}") == created.session_id

        await redis.delete(result_key, session_key)
        restored = await service.create_session(request)
        assert restored.session_id == created.session_id
        assert questions.calls == 1

        current = await service.current_question(created.session_id)
        assert current["completed"] is False
        await service.save_answer(created.session_id, 0, "事务具有 ACID")
        saved_answers = await repository.answers(created.session_id)
        assert [(item.question_index, item.user_answer) for item in saved_answers] == [
            (0, "事务具有 ACID")
        ]

        response = await service.submit_answer(
            created.session_id,
            0,
            "事务保证原子性",
        )
        assert response.has_next_question is True
        assert response.current_index == 1
        with pytest.raises(BusinessException, match="无效的问题索引"):
            await service.submit_answer(created.session_id, 99, "无效")

        await service.complete(created.session_id)
        stream_messages = await redis.xrange(INTERVIEW_EVALUATE.key)
        assert len(stream_messages) == 1
        assert stream_messages[0][1] == {
            "sessionId": created.session_id,
            "retryCount": "0",
        }
        with pytest.raises(BusinessException, match="面试已完成"):
            await service.complete(created.session_id)

        report = await service.generate_report(created.session_id)
        assert report.overall_score == 40
        detail = await service.detail(created.session_id)
        assert detail.status == "EVALUATED"
        assert detail.evaluate_status == "PENDING"
        assert [item.user_answer for item in detail.answers] == [
            "事务保证原子性",
            None,
        ]
        assert [item.score for item in detail.answers] == [80, 0]

        pdf, headers = await service.export_pdf(created.session_id)
        visible = extract_text(BytesIO(pdf))
        assert "模拟面试报告" in visible
        assert "会话ID: 1111111111111111" in visible
        assert "固定 fake 总评" in visible
        assert "事务保证原子性" in visible
        assert headers["Content-Type"] == "application/pdf"

        await service.delete(created.session_id)
        assert all(item.session_id != created.session_id for item in await service.list_sessions())
        stale = await service.get_session(created.session_id)
        assert stale.session_id == created.session_id
    finally:
        await cleanup(database, redis)
        await blocking.shutdown()
        await redis.aclose()
        await database.close()


@pytest.mark.asyncio
async def test_real_stream_worker_updates_status_and_acks_in_order() -> None:
    assert REDIS_URL is not None
    database = Database(integration_settings())
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await cleanup(database, redis)
    repository = InterviewRepository(database.sessions, now=lambda: FIXED_NOW)
    streams = RedisStreamService(redis)
    evaluation = ExplicitFakeEvaluationService()
    entity = await repository.create_session(
        session_id="3333333333333333",
        resume_id=None,
        questions=[
            InterviewQuestion(
                question_index=0,
                question="解释索引",
                type="DATABASE",
                category="数据库",
                user_answer=None,
            )
        ],
        llm_provider="default",
        skill_id="java-backend",
        difficulty="mid",
        request_id="interview-integration-worker",
    )
    del entity
    await repository.save_answer(
        "3333333333333333",
        0,
        "解释索引",
        "数据库",
        "索引加速查询",
        0,
        None,
    )
    await repository.update_session_status("3333333333333333", "COMPLETED")
    await repository.update_evaluate_status(
        "3333333333333333",
        "PENDING",
        None,
    )
    await streams.ensure_group(INTERVIEW_EVALUATE)
    message_id = await streams.add(
        INTERVIEW_EVALUATE.key,
        {"sessionId": "3333333333333333", "retryCount": "0"},
        message_id="10-0",
    )
    message = (
        await streams.read_batch(
            INTERVIEW_EVALUATE,
            "evaluate-consumer-integration",
            block_ms=10,
            pending_idle_ms=60_000,
        )
    )[0]
    consumer = SequentialStreamConsumer(
        streams,
        INTERVIEW_EVALUATE,
        "evaluate-consumer-integration",
        InterviewEvaluateHandler(
            repository,
            streams,
            evaluation,  # type: ignore[arg-type]
            ExplicitFakeRegistry(),  # type: ignore[arg-type]
        ),
    )

    try:
        assert message.message_id == message_id
        await consumer.process_message(message)
        record = await repository.find_session("3333333333333333")
        assert record is not None
        assert record.session.status == "EVALUATED"
        assert record.session.evaluate_status == "COMPLETED"
        assert evaluation.calls == 1
        pending = await redis.xpending(
            INTERVIEW_EVALUATE.key,
            INTERVIEW_EVALUATE.group,
        )
        assert pending["pending"] == 0
    finally:
        await cleanup(database, redis)
        await redis.aclose()
        await database.close()
