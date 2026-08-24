from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

import pytest

from interview_guide.common.ai.adapter import ChatResult, ProviderConfig
from interview_guide.common.ai.prompts import PromptRepository, PromptSanitizer
from interview_guide.common.ai.skills import SkillRepository
from interview_guide.common.ai.structured import StructuredInvocation
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import (
    InterviewQuestionRecord,
    InterviewSession,
    VoiceInterviewSession,
)
from interview_guide.modules.interview.models import (
    CategoryScore,
    CreateInterviewRequest,
    InterviewReportDTO,
    QuestionGroupEvaluationDTO,
    TurnAction,
    TurnDecisionOutput,
    TurnEvaluationDTO,
)
from interview_guide.modules.interview.question import InterviewSkillLibrary
from interview_guide.modules.interview.repository import SessionAggregate
from interview_guide.modules.interview.turn import InterviewTurnDecisionService
from interview_guide.modules.voice_interview.models import CreateVoiceSessionRequest
from interview_guide.modules.voice_interview.service import VoiceInterviewService

RESOURCES = Path(__file__).resolve().parents[2] / "resources"
PROVIDER = ProviderConfig(
    provider_id="explicit-fake",
    base_url="http://127.0.0.1",
    api_key="explicit-fake",
    model="explicit-fake",
)


class ExplicitFakeStructured:
    def __init__(self, output: TurnDecisionOutput) -> None:
        self.output = output
        self.calls = 0

    async def invoke_with_metadata(self, *args: object, **kwargs: object):
        del args, kwargs
        self.calls += 1
        return StructuredInvocation(
            value=self.output,
            response=ChatResult(
                content="{}",
                message={},
                usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                raw={},
            ),
        )


def settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="unit-test-key",
        APP_INTERVIEW_FOLLOW_UP_COUNT=1,
        APP_INTERVIEW_TURN_CONFIDENCE_THRESHOLD=0.65,
    )


def aggregate(*, follow_up_count: int = 0, max_follow_ups: int = 1) -> SessionAggregate:
    now = datetime(2026, 8, 19, 12, 0)
    session = InterviewSession(
        id=1,
        channel="TEXT",
        completed_at=None,
        context_json=None,
        created_at=now,
        current_question_id=uuid.uuid4(),
        difficulty="mid",
        evaluate_error=None,
        evaluate_status=None,
        improvements_json=None,
        interview_category=None,
        knowledge_base_id=None,
        llm_provider="explicit-fake",
        max_follow_ups_per_main=max_follow_ups,
        overall_feedback=None,
        overall_score=None,
        planned_main_question_count=2,
        reference_answers_json=None,
        request_id=None,
        resume_id=None,
        session_id="session-1",
        skill_id="java-backend",
        status="IN_PROGRESS",
        strengths_json=None,
    )
    main_id = session.current_question_id
    assert main_id is not None
    questions = [
        InterviewQuestionRecord(
            id=main_id,
            interview_session_id=1,
            kind="MAIN",
            phase=None,
            main_order=0,
            follow_up_order=0,
            parent_question_id=None,
            question="Redis缓存穿透怎么处理？",
            type="REDIS",
            category="Redis",
            topic_summary="缓存穿透",
            reference_answer=None,
            key_points_json=None,
            scoring_rubric=None,
            source_context=None,
            source_question_id=None,
            created_at=now,
        ),
        InterviewQuestionRecord(
            id=uuid.uuid4(),
            interview_session_id=1,
            kind="MAIN",
            phase=None,
            main_order=1,
            follow_up_order=0,
            parent_question_id=None,
            question="解释事务隔离级别。",
            type="DATABASE",
            category="数据库",
            topic_summary="事务隔离",
            reference_answer=None,
            key_points_json=None,
            scoring_rubric=None,
            source_context=None,
            source_question_id=None,
            created_at=now,
        ),
    ]
    for index in range(follow_up_count):
        question = InterviewQuestionRecord(
            id=uuid.uuid4(),
            interview_session_id=1,
            kind="FOLLOW_UP",
            phase=None,
            main_order=0,
            follow_up_order=index + 1,
            parent_question_id=main_id,
            question="如何应对恶意请求不存在的key？",
            type="REDIS",
            category="Redis",
            topic_summary="恶意空key",
            reference_answer=None,
            key_points_json=None,
            scoring_rubric=None,
            source_context=None,
            source_question_id=None,
            created_at=now,
        )
        questions.append(question)
    return SessionAggregate(session, "", questions, [])


def decision_service(structured: ExplicitFakeStructured) -> InterviewTurnDecisionService:
    return InterviewTurnDecisionService(
        structured,  # type: ignore[arg-type]
        PromptRepository(RESOURCES),
        PromptSanitizer(),
        InterviewSkillLibrary(SkillRepository(RESOURCES), RESOURCES),
        settings(),
    )


@pytest.mark.asyncio
async def test_follow_up_limit_skips_model_call() -> None:
    structured = ExplicitFakeStructured(
        TurnDecisionOutput(
            action="FOLLOW_UP",
            acknowledgement="需要继续深入。",
            followUpQuestion="如何落地？",
            reasonCode="MISSING_DETAIL",
            reason="缺少细节",
            targetTopic="落地",
            confidence=0.9,
        )
    )
    result = await decision_service(structured).decide(
        PROVIDER,
        aggregate(follow_up_count=1, max_follow_ups=1),
        "可以用布隆过滤器。",
    )

    assert result.action == TurnAction.NEXT_MAIN
    assert result.reason_code == "FOLLOW_UP_LIMIT_REACHED"
    assert structured.calls == 0


@pytest.mark.asyncio
async def test_model_can_create_answer_specific_follow_up_once() -> None:
    structured = ExplicitFakeStructured(
        TurnDecisionOutput(
            action="FOLLOW_UP",
            acknowledgement="你提到了布隆过滤器。",
            followUpQuestion="布隆过滤器误判时如何避免影响正常请求？",
            reasonCode="MISSING_TRADEOFF",
            reason="没有说明误判处理",
            targetTopic="布隆过滤器误判",
            confidence=0.92,
        )
    )
    result = await decision_service(structured).decide(
        PROVIDER,
        aggregate(),
        "我会使用布隆过滤器。",
    )

    assert result.action == TurnAction.FOLLOW_UP
    assert result.follow_up_question == "布隆过滤器误判时如何避免影响正常请求？"
    assert result.total_tokens == 15
    assert structured.calls == 1


@pytest.mark.asyncio
async def test_low_confidence_follow_up_becomes_next_main() -> None:
    structured = ExplicitFakeStructured(
        TurnDecisionOutput(
            action="FOLLOW_UP",
            acknowledgement="好的。",
            followUpQuestion="再说一点？",
            reasonCode="UNCERTAIN",
            reason="不确定",
            targetTopic="其他",
            confidence=0.2,
        )
    )
    result = await decision_service(structured).decide(
        PROVIDER,
        aggregate(),
        "完整回答",
    )

    assert result.action == TurnAction.NEXT_MAIN
    assert result.follow_up_question is None
    assert structured.calls == 1


def test_request_and_voice_duration_validation() -> None:
    assert CreateInterviewRequest().question_count == 8
    request = CreateInterviewRequest(
        questionCount=5,
        skillId="java-backend",
        requestId="request_1234",
    )
    assert request.request_id == "request_1234"
    voice = CreateVoiceSessionRequest(
        skillId="java-backend",
        plannedDuration=30,
        requestId="voice_123456",
    )
    assert voice.planned_duration == 30
    with pytest.raises(ValueError, match="5的倍数"):
        CreateVoiceSessionRequest(skillId="java-backend", plannedDuration=17)


def test_voice_session_response_uses_deployment_neutral_websocket_path() -> None:
    response = VoiceInterviewService._response(
        VoiceInterviewSession(
            id=42,
            interview_session_id=1,
            role_type="backend",
            current_phase="TECH",
            status="IN_PROGRESS",
            start_time=None,
            planned_duration=30,
        ),
        "session-1",
    )

    assert response.web_socket_url == "/ws/voice-interview/42"


def test_voice_phase_allocation_is_duration_based_and_weighted() -> None:
    phases = VoiceInterviewService._question_phases(
        CreateVoiceSessionRequest(
            skillId="java-backend",
            plannedDuration=30,
            introEnabled=False,
            techEnabled=True,
            projectEnabled=True,
            hrEnabled=True,
        ),
        6,
    )
    assert phases == ["TECH", "TECH", "TECH", "PROJECT", "PROJECT", "HR"]


def test_report_json_dump_serializes_question_uuids() -> None:
    question_id = uuid.uuid4()
    report = InterviewReportDTO(
        session_id="session-1",
        planned_main_questions=1,
        answered_main_questions=1,
        overall_score=80,
        category_scores=[CategoryScore(category="Redis", score=80, question_count=1)],
        question_groups=[
            QuestionGroupEvaluationDTO(
                main_question=TurnEvaluationDTO(
                    question_id=question_id,
                    question="如何治理缓存穿透？",
                    answer="布隆过滤器和空值缓存。",
                    score=80,
                    feedback="回答完整。",
                    reference_answer=None,
                    key_points=[],
                ),
                follow_ups=[],
                group_score=80,
                group_feedback="具备落地思路。",
                category="Redis",
            )
        ],
        overall_feedback="整体表现良好。",
        strengths=["方案完整"],
        improvements=[],
    )

    document = report.model_dump(mode="json", by_alias=True)

    assert document["questionGroups"][0]["mainQuestion"]["questionId"] == str(question_id)
