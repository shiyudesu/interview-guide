from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, cast
from urllib.parse import urlsplit

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, select

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import (
    VoiceInterviewEvaluation,
    VoiceInterviewMessage,
    VoiceInterviewSession,
)
from interview_guide.common.db.session import Database
from interview_guide.common.redis.streams import (
    VOICE_EVALUATE,
    RedisStreamService,
    SequentialStreamConsumer,
)
from interview_guide.modules.interview.models import (
    InterviewReportDTO,
    QuestionEvaluation,
    ReferenceAnswer,
)
from interview_guide.modules.voice_interview.evaluation import (
    VoiceEvaluatePayload,
    VoiceEvaluateStreamHandler,
    VoiceInterviewEvaluationService,
)
from interview_guide.modules.voice_interview.repository import VoiceInterviewRepository
from interview_guide.modules.voice_interview.service import (
    VoiceEvaluationProducer,
    VoiceInterviewService,
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
FIXED_NOW = datetime(2026, 8, 17, 8, 0)
PROVIDER = ProviderConfig(
    provider_id="explicit-fake-voice-evaluation",
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
        APP_AI_CONFIG_ENCRYPTION_KEY="voice-evaluation-integration-key",
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
        await session.execute(delete(VoiceInterviewEvaluation))
        await session.execute(delete(VoiceInterviewMessage))
        await session.execute(delete(VoiceInterviewSession))
    await redis.delete(VOICE_EVALUATE.key)
    cache_keys = [
        key
        async for key in redis.scan_iter(
            match="voice:interview:session:*",
        )
    ]
    if cache_keys:
        await redis.delete(*cache_keys)


async def seed_session(
    database: Database,
    *,
    status: str = "COMPLETED",
    evaluate_status: str | None = "PENDING",
    start_time: datetime = FIXED_NOW - timedelta(minutes=10),
    updated_at: datetime = FIXED_NOW - timedelta(minutes=5),
) -> int:
    async with database.sessions() as session, session.begin():
        entity = VoiceInterviewSession(
            actual_duration=600 if status == "COMPLETED" else None,
            created_at=start_time,
            current_phase="COMPLETED" if status == "COMPLETED" else "TECH",
            difficulty="mid",
            end_time=FIXED_NOW if status == "COMPLETED" else None,
            evaluate_error=None,
            evaluate_status=evaluate_status,
            hr_enabled=True,
            intro_enabled=False,
            llm_provider="default",
            planned_duration=30,
            project_enabled=True,
            role_type="Java 后端开发",
            skill_id="java-backend",
            start_time=start_time,
            status=status,
            tech_enabled=True,
            updated_at=updated_at,
            user_id="default",
        )
        session.add(entity)
        await session.flush()
        return entity.id


async def seed_dialogue(database: Database, session_id: int) -> None:
    async with database.sessions() as session, session.begin():
        session.add_all(
            [
                VoiceInterviewMessage(
                    ai_generated_text="请介绍一下自己",
                    created_at=FIXED_NOW - timedelta(minutes=8),
                    message_type="DIALOGUE",
                    phase="TECH",
                    sequence_num=1,
                    session_id=session_id,
                    timestamp=FIXED_NOW - timedelta(minutes=8),
                    user_recognized_text=None,
                ),
                VoiceInterviewMessage(
                    ai_generated_text="请介绍项目中的 Redis 设计",
                    created_at=FIXED_NOW - timedelta(minutes=7),
                    message_type="DIALOGUE",
                    phase="TECH",
                    sequence_num=2,
                    session_id=session_id,
                    timestamp=FIXED_NOW - timedelta(minutes=7),
                    user_recognized_text="我是 Java 后端工程师",
                ),
                VoiceInterviewMessage(
                    ai_generated_text=None,
                    created_at=FIXED_NOW - timedelta(minutes=6),
                    message_type="DIALOGUE",
                    phase="TECH",
                    sequence_num=3,
                    session_id=session_id,
                    timestamp=FIXED_NOW - timedelta(minutes=6),
                    user_recognized_text="使用 RDB 和 AOF",
                ),
            ]
        )


class ExplicitFakeRegistry:
    async def get_chat(self, provider_id: str | None = None) -> ProviderConfig:
        assert provider_id is None
        return PROVIDER


class ExplicitFakeSkills:
    def evaluation_reference_section(self, skill_id: str | None) -> str:
        assert skill_id == "java-backend"
        return "固定 Java Skill 参考基线"


class ExplicitFakeUnifiedEvaluation:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[list[Any]] = []

    async def evaluate(
        self,
        provider: ProviderConfig,
        session_id: str,
        records: list[Any],
        resume_text: str | None,
        reference_context: str | None,
    ) -> InterviewReportDTO:
        assert provider is PROVIDER
        assert resume_text is None
        assert reference_context == "固定 Java Skill 参考基线"
        self.calls.append(records)
        if self.fail:
            raise RuntimeError("explicit fake evaluation failure")
        return InterviewReportDTO(
            session_id=session_id,
            total_questions=len(records),
            overall_score=75,
            category_scores=[],
            question_details=[
                QuestionEvaluation(
                    question_index=item.question_index,
                    question=item.question,
                    category=item.category,
                    user_answer=item.user_answer,
                    score=75,
                    feedback="固定 fake 反馈",
                )
                for item in records
            ],
            overall_feedback="固定 fake 总评",
            strengths=["表达清晰"],
            improvements=["补充细节"],
            reference_answers=[
                ReferenceAnswer(
                    question_index=item.question_index,
                    question=item.question,
                    reference_answer="固定 fake 参考答案",
                    key_points=["固定 fake 要点"],
                )
                for item in records
            ],
        )


def build_consumer(
    database: Database,
    redis: Redis,
    now: Callable[[], datetime],
    unified: ExplicitFakeUnifiedEvaluation,
    consumer_name: str,
) -> SequentialStreamConsumer[VoiceEvaluatePayload]:
    repository = VoiceInterviewRepository(database.sessions, now)
    streams = RedisStreamService(redis)
    producer = VoiceEvaluationProducer(streams, repository, redis)
    status_service = VoiceInterviewService(repository, redis, producer, now)
    return SequentialStreamConsumer(
        streams,
        VOICE_EVALUATE,
        consumer_name,
        VoiceEvaluateStreamHandler(
            repository,
            streams,
            VoiceInterviewEvaluationService(
                repository,
                cast(Any, unified),
                cast(Any, ExplicitFakeRegistry()),
                cast(Any, ExplicitFakeSkills()),
                now,
            ),
            status_service,
        ),
    )


@pytest.mark.asyncio
async def test_real_postgres_redis_voice_worker_handles_empty_bad_missing_and_completed() -> None:
    assert REDIS_URL is not None
    database = Database(integration_settings())
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await cleanup(database, redis)
    valid_id = await seed_session(database)
    empty_id = await seed_session(database)
    completed_id = await seed_session(database, evaluate_status="COMPLETED")
    await seed_dialogue(database, valid_id)
    unified = ExplicitFakeUnifiedEvaluation()
    streams = RedisStreamService(redis)
    consumer = build_consumer(
        database,
        redis,
        lambda: FIXED_NOW,
        unified,
        "voice-evaluate-consumer-integration",
    )
    await streams.ensure_group(VOICE_EVALUATE)
    await redis.set(f"voice:interview:session:{valid_id}", "stale", ex=3600)
    await redis.set(f"voice:interview:session:{empty_id}", "stale", ex=3600)
    await redis.set(f"voice:interview:session:{completed_id}", "completed", ex=3600)
    for message_id, fields in (
        ("1-0", {"voiceSessionId": str(valid_id), "retryCount": "0"}),
        ("2-0", {"voiceSessionId": str(empty_id), "retryCount": "0"}),
        ("3-0", {"voiceSessionId": "9223372036854775807", "retryCount": "0"}),
        ("4-0", {"voiceSessionId": str(completed_id), "retryCount": "0"}),
        ("5-0", {"voiceSessionId": "bad", "retryCount": "0"}),
        ("6-0", {"retryCount": "0"}),
    ):
        await streams.add(VOICE_EVALUATE.key, fields, message_id=message_id)

    try:
        messages = await streams.read_batch(
            VOICE_EVALUATE,
            "voice-evaluate-consumer-integration",
            block_ms=10,
            pending_idle_ms=60_000,
        )
        for message in messages:
            await consumer.process_message(message)

        async with database.sessions() as session:
            valid = await session.get(VoiceInterviewSession, valid_id)
            empty = await session.get(VoiceInterviewSession, empty_id)
            completed = await session.get(VoiceInterviewSession, completed_id)
            evaluations = list(
                await session.scalars(
                    select(VoiceInterviewEvaluation).order_by(VoiceInterviewEvaluation.session_id)
                )
            )
        assert valid is not None and valid.evaluate_status == "COMPLETED"
        assert empty is not None and empty.evaluate_status == "COMPLETED"
        assert completed is not None and completed.evaluate_status == "COMPLETED"
        assert len(unified.calls) == 1
        assert len(evaluations) == 2
        assert evaluations[0].overall_score == 75
        assert evaluations[1].overall_score is None
        assert "暂无可评估内容" in str(evaluations[1].overall_feedback)
        pending = await redis.xpending(VOICE_EVALUATE.key, VOICE_EVALUATE.group)
        assert pending["pending"] == 0
        assert await redis.exists(f"voice:interview:session:{valid_id}") == 0
        assert await redis.exists(f"voice:interview:session:{empty_id}") == 0
        assert await redis.get(f"voice:interview:session:{completed_id}") == "completed"
    finally:
        await cleanup(database, redis)
        await redis.aclose()
        await database.close()


@pytest.mark.asyncio
async def test_real_postgres_redis_voice_worker_retries_three_times_then_fails() -> None:
    assert REDIS_URL is not None
    database = Database(integration_settings())
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await cleanup(database, redis)
    session_id = await seed_session(database)
    await seed_dialogue(database, session_id)
    unified = ExplicitFakeUnifiedEvaluation(fail=True)
    streams = RedisStreamService(redis)
    consumer_name = "voice-evaluate-consumer-retry"
    consumer = build_consumer(
        database,
        redis,
        lambda: FIXED_NOW,
        unified,
        consumer_name,
    )
    await streams.ensure_group(VOICE_EVALUATE)
    await streams.add(
        VOICE_EVALUATE.key,
        {"voiceSessionId": str(session_id), "retryCount": "0"},
        message_id="1-0",
    )

    try:
        for retry_count in range(4):
            messages = await streams.read_batch(
                VOICE_EVALUATE,
                consumer_name,
                block_ms=10,
                pending_idle_ms=60_000,
            )
            assert len(messages) == 1
            assert messages[0].retry_count == retry_count
            await consumer.process_message(messages[0])
            pending = await redis.xpending(
                VOICE_EVALUATE.key,
                VOICE_EVALUATE.group,
            )
            assert pending["pending"] == 0

        async with database.sessions() as session:
            entity = await session.get(VoiceInterviewSession, session_id)
            evaluation = await session.scalar(
                select(VoiceInterviewEvaluation).where(
                    VoiceInterviewEvaluation.session_id == session_id
                )
            )
        assert entity is not None
        assert entity.evaluate_status == "FAILED"
        assert entity.evaluate_error is not None
        assert entity.evaluate_error.startswith("语音面试评估 failed after retry 3:")
        assert evaluation is None
        assert len(unified.calls) == 4
        assert await redis.xlen(VOICE_EVALUATE.key) == 4
    finally:
        await cleanup(database, redis)
        await redis.aclose()
        await database.close()


@pytest.mark.asyncio
async def test_real_redis_voice_pending_is_reclaimed_after_consumer_crash() -> None:
    assert REDIS_URL is not None
    database = Database(integration_settings())
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await cleanup(database, redis)
    session_id = await seed_session(database)
    await seed_dialogue(database, session_id)
    unified = ExplicitFakeUnifiedEvaluation()
    streams = RedisStreamService(redis)
    await streams.ensure_group(VOICE_EVALUATE)
    await streams.add(
        VOICE_EVALUATE.key,
        {"voiceSessionId": str(session_id), "retryCount": "0"},
        message_id="1-0",
    )

    try:
        abandoned = await streams.read_batch(
            VOICE_EVALUATE,
            "voice-evaluate-consumer-crashed",
            block_ms=10,
            pending_idle_ms=60_000,
        )
        assert [message.message_id for message in abandoned] == ["1-0"]
        pending = await redis.xpending(VOICE_EVALUATE.key, VOICE_EVALUATE.group)
        assert pending["pending"] == 1

        await asyncio.sleep(0.02)
        reclaimed = await streams.read_batch(
            VOICE_EVALUATE,
            "voice-evaluate-consumer-replacement",
            block_ms=10,
            pending_idle_ms=10,
        )
        assert [message.message_id for message in reclaimed] == ["1-0"]
        replacement = build_consumer(
            database,
            redis,
            lambda: FIXED_NOW,
            unified,
            "voice-evaluate-consumer-replacement",
        )
        await replacement.process_message(reclaimed[0])

        async with database.sessions() as session:
            entity = await session.get(VoiceInterviewSession, session_id)
        assert entity is not None
        assert entity.evaluate_status == "COMPLETED"
        assert len(unified.calls) == 1
        pending = await redis.xpending(VOICE_EVALUATE.key, VOICE_EVALUATE.group)
        assert pending["pending"] == 0
    finally:
        await cleanup(database, redis)
        await redis.aclose()
        await database.close()


@pytest.mark.asyncio
async def test_real_postgres_redis_voice_recovery_matches_java_thresholds() -> None:
    assert REDIS_URL is not None
    database = Database(integration_settings())
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await cleanup(database, redis)
    stale_session_id = await seed_session(
        database,
        status="IN_PROGRESS",
        evaluate_status=None,
        start_time=FIXED_NOW - timedelta(hours=2, seconds=1),
        updated_at=FIXED_NOW - timedelta(hours=2, seconds=1),
    )
    pending_id = await seed_session(
        database,
        updated_at=FIXED_NOW - timedelta(minutes=3, seconds=1),
    )
    processing_id = await seed_session(
        database,
        evaluate_status="PROCESSING",
        updated_at=FIXED_NOW - timedelta(minutes=30, seconds=1),
    )
    for session_id in (stale_session_id, pending_id, processing_id):
        await redis.set(f"voice:interview:session:{session_id}", "stale", ex=3600)
    repository = VoiceInterviewRepository(database.sessions, lambda: FIXED_NOW)
    streams = RedisStreamService(redis)
    service = VoiceInterviewService(
        repository,
        redis,
        VoiceEvaluationProducer(streams, repository, redis),
        lambda: FIXED_NOW,
    )

    try:
        assert await service.cleanup_stale_sessions() == 3

        async with database.sessions() as session:
            stale = await session.get(VoiceInterviewSession, stale_session_id)
            pending = await session.get(VoiceInterviewSession, pending_id)
            processing = await session.get(VoiceInterviewSession, processing_id)
        assert stale is not None
        assert stale.status == "COMPLETED"
        assert stale.evaluate_status == "PENDING"
        assert stale.end_time == FIXED_NOW
        assert pending is not None and pending.evaluate_status == "PENDING"
        assert pending.updated_at == FIXED_NOW
        assert processing is not None
        assert processing.evaluate_status == "FAILED"
        assert processing.evaluate_error == "评估超时，请重新触发"
        assert [fields for _, fields in await redis.xrange(VOICE_EVALUATE.key)] == [
            {
                "voiceSessionId": str(stale_session_id),
                "retryCount": "0",
            },
            {
                "voiceSessionId": str(pending_id),
                "retryCount": "0",
            },
        ]
        cache_exists = [
            await redis.exists(f"voice:interview:session:{session_id}")
            for session_id in (stale_session_id, pending_id, processing_id)
        ]
        assert cache_exists == [0, 0, 0]
    finally:
        await cleanup(database, redis)
        await redis.aclose()
        await database.close()
