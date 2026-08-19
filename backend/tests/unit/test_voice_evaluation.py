from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, cast

import pytest

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.db.models import (
    VoiceInterviewMessage,
    VoiceInterviewSession,
)
from interview_guide.common.redis.streams import (
    VOICE_EVALUATE,
    SequentialStreamConsumer,
    StreamMessage,
)
from interview_guide.modules.interview.models import (
    InterviewReportDTO,
    QuestionEvaluation,
    ReferenceAnswer,
)
from interview_guide.modules.voice_interview.api import evaluation_detail
from interview_guide.modules.voice_interview.evaluation import (
    VoiceEvaluateStreamHandler,
    VoiceInterviewEvaluationService,
)
from interview_guide.modules.voice_interview.service import VoiceInterviewService

FIXED_NOW = datetime(2026, 8, 17, 8, 0)
PROVIDER = ProviderConfig(
    provider_id="explicit-fake",
    base_url="http://127.0.0.1",
    api_key="explicit-fake",
    model="explicit-fake",
)


def voice_session(
    session_id: int = 1,
    *,
    evaluate_status: str | None = "PENDING",
) -> VoiceInterviewSession:
    return VoiceInterviewSession(
        id=session_id,
        role_type="Java 后端开发",
        skill_id="java-backend",
        llm_provider="default",
        start_time=FIXED_NOW - timedelta(minutes=10),
        status="COMPLETED",
        current_phase="COMPLETED",
        evaluate_status=evaluate_status,
        updated_at=FIXED_NOW - timedelta(minutes=5),
    )


class ExplicitFakeEvaluationRepository:
    def __init__(
        self,
        session: VoiceInterviewSession,
        messages: list[VoiceInterviewMessage],
    ) -> None:
        self.session = session
        self.message_rows = messages
        self.saved_evaluation: Any | None = None
        self.saved_empty: tuple[int, str, datetime | None] | None = None

    async def find_session(self, session_id: int) -> VoiceInterviewSession | None:
        return self.session if session_id == self.session.id else None

    async def messages(self, session_id: int) -> list[VoiceInterviewMessage]:
        assert session_id == self.session.id
        return self.message_rows

    async def save_evaluation(self, entity: Any) -> None:
        self.saved_evaluation = entity

    async def save_empty_evaluation(
        self,
        session_id: int,
        role_type: str,
        interview_date: datetime | None,
    ) -> None:
        self.saved_empty = (session_id, role_type, interview_date)


class ExplicitFakeRegistry:
    def __init__(self) -> None:
        self.provider_ids: list[str | None] = []

    async def get_chat(self, provider_id: str | None = None) -> ProviderConfig:
        self.provider_ids.append(provider_id)
        return PROVIDER


class ExplicitFakeSkills:
    def __init__(self) -> None:
        self.skill_ids: list[str | None] = []

    def evaluation_reference_section(self, skill_id: str | None) -> str:
        self.skill_ids.append(skill_id)
        return "固定 Skill 参考基线"


class ExplicitFakeUnifiedEvaluation:
    def __init__(self) -> None:
        self.calls: list[tuple[ProviderConfig, str, list[Any], str | None, str | None]] = []

    async def evaluate(
        self,
        provider: ProviderConfig,
        session_id: str,
        records: list[Any],
        resume_text: str | None,
        reference_context: str | None,
    ) -> InterviewReportDTO:
        self.calls.append((provider, session_id, records, resume_text, reference_context))
        return InterviewReportDTO(
            session_id=session_id,
            total_questions=len(records),
            overall_score=80,
            category_scores=[],
            question_details=[
                QuestionEvaluation(
                    question_index=item.question_index,
                    question=item.question,
                    category=item.category,
                    user_answer=item.user_answer,
                    score=80,
                    feedback=f"固定 fake 反馈 {item.question_index}",
                )
                for item in records
            ],
            overall_feedback="固定 fake 总评",
            strengths=["表达清晰"],
            improvements=["补充边界"],
            reference_answers=[
                ReferenceAnswer(
                    question_index=item.question_index,
                    question=item.question,
                    reference_answer=f"固定参考答案 {item.question_index}",
                    key_points=["固定要点"],
                )
                for item in records
            ],
        )


@pytest.mark.asyncio
async def test_explicit_fake_empty_voice_dialogue_saves_compatibility_empty_evaluation() -> None:
    repository = ExplicitFakeEvaluationRepository(voice_session(), [])
    unified = ExplicitFakeUnifiedEvaluation()
    registry = ExplicitFakeRegistry()
    skills = ExplicitFakeSkills()
    service = VoiceInterviewEvaluationService(
        cast(Any, repository),
        cast(Any, unified),
        cast(Any, registry),
        cast(Any, skills),
        lambda: FIXED_NOW,
    )

    await service.generate(1)

    assert repository.saved_empty == (
        1,
        "Java 后端开发",
        FIXED_NOW - timedelta(minutes=10),
    )
    assert repository.saved_evaluation is None
    assert unified.calls == []
    assert registry.provider_ids == []


@pytest.mark.asyncio
async def test_fake_voice_evaluation_builds_contract_order_and_references() -> None:
    repository = ExplicitFakeEvaluationRepository(
        voice_session(),
        [
            VoiceInterviewMessage(
                id=1,
                session_id=1,
                message_type="DIALOGUE",
                sequence_num=1,
                ai_generated_text="请介绍一下自己",
                user_recognized_text=None,
            ),
            VoiceInterviewMessage(
                id=2,
                session_id=1,
                message_type="DIALOGUE",
                sequence_num=2,
                ai_generated_text="请介绍项目中的缓存设计",
                user_recognized_text="我是后端工程师",
            ),
            VoiceInterviewMessage(
                id=3,
                session_id=1,
                message_type="DIALOGUE",
                sequence_num=3,
                ai_generated_text="你的职业规划是什么",
                user_recognized_text="使用 Redis 缓存",
            ),
            VoiceInterviewMessage(
                id=4,
                session_id=1,
                message_type="DIALOGUE",
                sequence_num=4,
                ai_generated_text=None,
                user_recognized_text="持续深入后端",
            ),
        ],
    )
    unified = ExplicitFakeUnifiedEvaluation()
    registry = ExplicitFakeRegistry()
    skills = ExplicitFakeSkills()
    service = VoiceInterviewEvaluationService(
        cast(Any, repository),
        cast(Any, unified),
        cast(Any, registry),
        cast(Any, skills),
        lambda: FIXED_NOW,
    )

    await service.generate(1)

    assert registry.provider_ids == [None]
    assert skills.skill_ids == ["java-backend"]
    records = unified.calls[0][2]
    assert [
        (item.question_index, item.question, item.category, item.user_answer) for item in records
    ] == [
        (0, "请介绍一下自己", "自我介绍", "我是后端工程师"),
        (1, "请介绍项目中的缓存设计", "项目深挖", "使用 Redis 缓存"),
        (2, "你的职业规划是什么", "HR问题", "持续深入后端"),
    ]
    assert unified.calls[0][3:] == (None, "固定 Skill 参考基线")
    saved = repository.saved_evaluation
    assert saved is not None
    assert saved.overall_score == 80
    assert json.loads(saved.question_evaluations_json)[0] == {
        "questionIndex": 0,
        "question": "请介绍一下自己",
        "category": "自我介绍",
        "userAnswer": "我是后端工程师",
        "score": 80,
        "feedback": "固定 fake 反馈 0",
    }
    assert json.loads(saved.reference_answers_json)[0] == {
        "questionIndex": 0,
        "question": "请介绍一下自己",
        "referenceAnswer": "固定参考答案 0",
        "keyPoints": ["固定要点"],
    }
    detail = evaluation_detail(saved)
    assert detail.answers[0].reference_answer == "固定参考答案 0"
    assert detail.answers[0].key_points == ["固定要点"]


class ExplicitFakeStatusService:
    def __init__(self) -> None:
        self.statuses: list[tuple[int, str, str | None]] = []

    async def update_evaluate_status(
        self,
        session_id: int,
        status: str,
        error: str | None,
    ) -> None:
        self.statuses.append((session_id, status, error))


class ExplicitFailingStreams:
    async def add(self, *args: object, **kwargs: object) -> str:
        del args, kwargs
        raise RuntimeError("explicit retry failure")


@pytest.mark.asyncio
async def test_voice_handler_parses_bad_payload_and_marks_retry_failure() -> None:
    repository = ExplicitFakeEvaluationRepository(voice_session(), [])
    status = ExplicitFakeStatusService()
    handler = VoiceEvaluateStreamHandler(
        cast(Any, repository),
        cast(Any, ExplicitFailingStreams()),
        cast(Any, None),
        status,
    )

    assert await handler.parse(StreamMessage("1-0", {})) is None
    with pytest.raises(ValueError):
        await handler.parse(StreamMessage("2-0", {"voiceSessionId": "bad"}))
    payload = await handler.parse(StreamMessage("3-0", {"voiceSessionId": "1"}))
    assert payload is not None
    with pytest.raises(RuntimeError, match="explicit retry failure"):
        await handler.retry(payload, 1)
    assert status.statuses == [(1, "FAILED", "重试入队失败: explicit retry failure")]


class ExplicitEventStreams:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def add(
        self,
        stream_key: str,
        fields: dict[str, str],
        **kwargs: object,
    ) -> str:
        del stream_key, kwargs
        self.events.append(f"requeue:{fields['retryCount']}")
        return "2-0"

    async def ack(self, definition: object, *message_ids: str) -> int:
        del definition
        self.events.extend(f"ack:{message_id}" for message_id in message_ids)
        return len(message_ids)


class ExplicitEventStatusService:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def update_evaluate_status(
        self,
        session_id: int,
        status: str,
        error: str | None,
    ) -> None:
        del session_id, error
        self.events.append(f"status:{status}")


class ExplicitFailingEvaluation:
    async def generate(self, session_id: int) -> None:
        del session_id
        raise RuntimeError("explicit processing failure")


@pytest.mark.asyncio
async def test_voice_retry_and_final_failure_happen_before_ack() -> None:
    repository = ExplicitFakeEvaluationRepository(voice_session(), [])
    retry_events: list[str] = []
    retry_streams = ExplicitEventStreams(retry_events)
    retry_consumer = SequentialStreamConsumer(
        cast(Any, retry_streams),
        VOICE_EVALUATE,
        "voice-evaluate-consumer-explicit-fake",
        VoiceEvaluateStreamHandler(
            cast(Any, repository),
            cast(Any, retry_streams),
            cast(Any, ExplicitFailingEvaluation()),
            ExplicitEventStatusService(retry_events),
        ),
    )

    await retry_consumer.process_message(
        StreamMessage(
            "1-0",
            {"voiceSessionId": "1", "retryCount": "0"},
        )
    )

    assert retry_events == [
        "status:PROCESSING",
        "requeue:1",
        "ack:1-0",
    ]

    final_events: list[str] = []
    final_streams = ExplicitEventStreams(final_events)
    final_consumer = SequentialStreamConsumer(
        cast(Any, final_streams),
        VOICE_EVALUATE,
        "voice-evaluate-consumer-explicit-fake",
        VoiceEvaluateStreamHandler(
            cast(Any, repository),
            cast(Any, final_streams),
            cast(Any, ExplicitFailingEvaluation()),
            ExplicitEventStatusService(final_events),
        ),
    )
    await final_consumer.process_message(
        StreamMessage(
            "4-0",
            {"voiceSessionId": "1", "retryCount": "3"},
        )
    )
    assert final_events == [
        "status:PROCESSING",
        "status:FAILED",
        "ack:4-0",
    ]


class ExplicitFakeRecoveryRepository:
    def __init__(self) -> None:
        self.thresholds: list[tuple[str, datetime]] = []
        self.sessions = {
            1: voice_session(1, evaluate_status=None),
            2: voice_session(2, evaluate_status="PENDING"),
            3: voice_session(3, evaluate_status="PROCESSING"),
        }

    async def stale_in_progress(
        self,
        before: datetime,
    ) -> list[VoiceInterviewSession]:
        self.thresholds.append(("IN_PROGRESS", before))
        self.sessions[1].status = "IN_PROGRESS"
        return [self.sessions[1]]

    async def stale_evaluations(
        self,
        status: str,
        before: datetime,
    ) -> list[VoiceInterviewSession]:
        self.thresholds.append((status, before))
        return [self.sessions[2 if status == "PENDING" else 3]]

    async def end_session(
        self,
        session_id: int,
        *,
        only_if_in_progress: bool,
    ) -> VoiceInterviewSession | None:
        del only_if_in_progress
        entity = self.sessions[session_id]
        entity.status = "COMPLETED"
        entity.evaluate_status = "PENDING"
        return entity

    async def update_evaluate_status(
        self,
        session_id: int,
        status: str,
        error: str | None,
    ) -> bool:
        entity = self.sessions[session_id]
        entity.evaluate_status = status
        entity.evaluate_error = error
        return True


class ExplicitFakeRedis:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def delete(self, *keys: str) -> int:
        self.deleted.extend(keys)
        return len(keys)


class ExplicitFakeProducer:
    def __init__(self) -> None:
        self.sent: list[tuple[int, int]] = []

    async def send(self, session_id: int, retry_count: int = 0) -> bool:
        self.sent.append((session_id, retry_count))
        return True


@pytest.mark.asyncio
async def test_voice_recovery_uses_contract_thresholds_and_cache_invalidation() -> None:
    repository = ExplicitFakeRecoveryRepository()
    redis = ExplicitFakeRedis()
    producer = ExplicitFakeProducer()
    service = VoiceInterviewService(
        cast(Any, repository),
        cast(Any, redis),
        cast(Any, producer),
        lambda: FIXED_NOW,
    )

    assert await service.cleanup_stale_sessions() == 3

    assert repository.thresholds == [
        ("IN_PROGRESS", FIXED_NOW - timedelta(hours=2)),
        ("PENDING", FIXED_NOW - timedelta(minutes=3)),
        ("PROCESSING", FIXED_NOW - timedelta(minutes=30)),
    ]
    assert producer.sent == [(1, 0), (2, 0)]
    assert repository.sessions[1].status == "COMPLETED"
    assert repository.sessions[1].evaluate_status == "PENDING"
    assert repository.sessions[2].evaluate_status == "PENDING"
    assert repository.sessions[3].evaluate_status == "FAILED"
    assert repository.sessions[3].evaluate_error == "评估超时，请重新触发"
    assert redis.deleted == [
        "voice:interview:session:1",
        "voice:interview:session:2",
        "voice:interview:session:3",
    ]
