from __future__ import annotations

import os
import uuid
from contextlib import suppress
from datetime import datetime, timedelta
from urllib.parse import urlsplit

import pytest

from interview_guide.common.config.settings import Settings
from interview_guide.common.db.session import Database
from interview_guide.modules.interview.models import (
    InterviewChannel,
    PlannedInterviewQuestion,
    TurnAction,
    TurnDecisionStatus,
)
from interview_guide.modules.interview.repository import InterviewRepository

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(POSTGRES_URL is None, reason="TEST_POSTGRES_URL is required"),
]


def database_settings() -> Settings:
    assert POSTGRES_URL is not None
    parsed = urlsplit(POSTGRES_URL)
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="integration-key",
        POSTGRES_HOST=parsed.hostname or "127.0.0.1",
        POSTGRES_PORT=parsed.port or 5432,
        POSTGRES_DB=parsed.path.removeprefix("/"),
        POSTGRES_USER=parsed.username or "postgres",
        POSTGRES_PASSWORD=parsed.password or "",
    )


@pytest.mark.asyncio
async def test_normalized_turn_transaction_and_idempotency() -> None:
    database = Database(database_settings())
    repository = InterviewRepository(database.sessions, datetime.now)
    session_id = f"it-{uuid.uuid4().hex[:12]}"
    try:
        aggregate = await repository.create_session(
            session_id=session_id,
            channel=InterviewChannel.TEXT,
            resume_id=None,
            questions=[
                PlannedInterviewQuestion(
                    question="解释Redis缓存穿透。",
                    type="REDIS",
                    category="Redis",
                ),
                PlannedInterviewQuestion(
                    question="解释事务隔离级别。",
                    type="DATABASE",
                    category="数据库",
                ),
            ],
            max_follow_ups_per_main=1,
            llm_provider=None,
            skill_id="java-backend",
            difficulty="mid",
            request_id=f"create_{uuid.uuid4().hex[:12]}",
        )
        current = aggregate.questions[0]
        request_id = f"answer_{uuid.uuid4().hex[:12]}"
        started = await repository.begin_turn(
            session_id,
            current.id,
            request_id,
            "使用布隆过滤器。",
            "hash",
            datetime.now() + timedelta(seconds=30),
        )
        replay = await repository.begin_turn(
            session_id,
            current.id,
            request_id,
            "使用布隆过滤器。",
            "hash",
            datetime.now() + timedelta(seconds=30),
        )
        assert replay.existing is True
        assert replay.turn.id == started.turn.id

        finalized = await repository.finalize_turn(
            session_id,
            started.turn.id,
            action=TurnAction.FOLLOW_UP,
            acknowledgement="你提到了布隆过滤器。",
            follow_up_question="误判时如何处理？",
            decision_reason="缺少取舍",
            reason_code="MISSING_TRADEOFF",
            target_topic="布隆过滤器误判",
            confidence=0.9,
            decision_status=TurnDecisionStatus.COMPLETED,
            provider_id="fake",
            model_name="fake",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            duration_ms=10,
            error=None,
        )
        assert finalized.turn.action == "FOLLOW_UP"
        assert finalized.aggregate.session.current_question_id == finalized.turn.next_question_id
        assert len(finalized.aggregate.questions) == 3
    finally:
        with suppress(Exception):
            await repository.delete_session(session_id)
        await database.close()
