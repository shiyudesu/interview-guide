from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, cast

import pytest

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.prompts import (
    PromptRepository,
    PromptSanitizer,
)
from interview_guide.common.ai.skills import SkillRepository
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.redis.streams import (
    INTERVIEW_EVALUATE,
    SequentialStreamConsumer,
    StreamMessage,
)
from interview_guide.modules.interview.cache import (
    CREATE_LOCK_LEASE_SECONDS,
    CREATE_LOCK_WAIT_SECONDS,
    CREATE_RESULT_TTL_SECONDS,
)
from interview_guide.modules.interview.evaluation import (
    BatchReportOutput,
    QaRecord,
    QuestionEvaluationOutput,
    SummaryOutput,
    UnifiedEvaluationService,
)
from interview_guide.modules.interview.models import (
    CreateInterviewRequest,
    InterviewSessionStatus,
)
from interview_guide.modules.interview.question import (
    InterviewQuestionService,
    InterviewSkillLibrary,
    JdCategoryListOutput,
    JdCategoryOutput,
    JdParseService,
    QuestionListOutput,
    QuestionOutput,
)

RESOURCES = Path(__file__).resolve().parents[2] / "resources"
PROVIDER = ProviderConfig(
    provider_id="explicit-fake",
    base_url="http://127.0.0.1",
    api_key="explicit-fake",
    model="explicit-fake",
)


class ExplicitFakeRegistry:
    async def get_chat(self, provider_id: str | None = None) -> ProviderConfig:
        del provider_id
        return PROVIDER


class ExplicitFakeQuestionStructured:
    def __init__(
        self,
        *,
        fail_resume: bool = False,
        fail_direction: bool = False,
    ) -> None:
        self.fail_resume = fail_resume
        self.fail_direction = fail_direction
        self.calls: list[tuple[str, int]] = []

    async def invoke(
        self,
        provider: ProviderConfig,
        system_prompt_with_format: str,
        user_prompt: str,
        output_type: type[Any],
        error_code: object,
        error_prefix: str,
        **kwargs: object,
    ) -> Any:
        del provider, system_prompt_with_format, output_type, error_code, kwargs
        count_match = re.search(r"请生成共 (-?\d+) 个", user_prompt)
        count = int(count_match.group(1)) if count_match else 0
        self.calls.append((error_prefix, count))
        if self.fail_resume and error_prefix.startswith("简历题"):
            raise BusinessException(ErrorCode.INTERVIEW_QUESTION_GENERATION_FAILED)
        if self.fail_direction and error_prefix.startswith("方向题"):
            raise BusinessException(ErrorCode.INTERVIEW_QUESTION_GENERATION_FAILED)
        return QuestionListOutput(
            questions=[
                QuestionOutput(
                    question=f"主问题{i + 1}",
                    type="java",
                    category="Java",
                    topicSummary=f"主题{i + 1}",
                    followUps=["追问一", "追问二"],
                )
                for i in range(max(0, count))
            ]
        )


class ExplicitFakeEvaluationStructured:
    def __init__(self) -> None:
        self.output_types: list[type[Any]] = []
        self.batch_calls = 0

    async def invoke(
        self,
        provider: ProviderConfig,
        system_prompt_with_format: str,
        user_prompt: str,
        output_type: type[Any],
        error_code: object,
        error_prefix: str,
        **kwargs: object,
    ) -> Any:
        del provider, system_prompt_with_format, user_prompt, error_code, error_prefix, kwargs
        self.output_types.append(output_type)
        if output_type is BatchReportOutput:
            self.batch_calls += 1
            if self.batch_calls == 2:
                raise RuntimeError("explicit fake batch failure")
            return BatchReportOutput(
                overallScore=70,
                overallFeedback="首批反馈",
                strengths=["准确"],
                improvements=["深入"],
                questionEvaluations=[
                    QuestionEvaluationOutput(
                        questionIndex=0,
                        score=80,
                        feedback="好",
                        referenceAnswer="参考一",
                        keyPoints=["要点一"],
                    ),
                    QuestionEvaluationOutput(
                        questionIndex=1,
                        score=60,
                        feedback="一般",
                        referenceAnswer="参考二",
                        keyPoints=["要点二"],
                    ),
                ],
            )
        if output_type is SummaryOutput:
            raise RuntimeError("explicit fake summary failure")
        raise AssertionError(output_type)


class ExplicitFakeJdStructured:
    async def invoke(
        self,
        provider: ProviderConfig,
        system_prompt_with_format: str,
        user_prompt: str,
        output_type: type[Any],
        error_code: object,
        error_prefix: str,
        **kwargs: object,
    ) -> Any:
        del provider, system_prompt_with_format, user_prompt, error_code, error_prefix, kwargs
        assert output_type is JdCategoryListOutput
        return JdCategoryListOutput(
            categories=[
                JdCategoryOutput(
                    key="JAVA",
                    label="Java",
                    priority="CORE",
                    ref="java-core.md",
                    shared=False,
                )
            ]
        )


def question_service(
    structured: ExplicitFakeQuestionStructured,
) -> InterviewQuestionService:
    return InterviewQuestionService(
        cast(Any, ExplicitFakeRegistry()),
        cast(Any, structured),
        PromptRepository(RESOURCES),
        PromptSanitizer(uuid_factory=lambda: uuid.UUID(int=0)),
        InterviewSkillLibrary(SkillRepository(RESOURCES), RESOURCES),
        follow_up_count=1,
    )


def test_create_request_keeps_compatibility_controller_defaults_without_extra_validation() -> None:
    request = CreateInterviewRequest.model_validate({})
    assert request.question_count == 0
    assert request.skill_id is None
    assert request.resume_text is None
    assert InterviewSessionStatus.CREATED.value == "CREATED"
    assert CREATE_LOCK_WAIT_SECONDS == 185
    assert CREATE_LOCK_LEASE_SECONDS == 600
    assert CREATE_RESULT_TTL_SECONDS == 86_400


@pytest.mark.asyncio
async def test_explicit_fake_direction_generation_caps_followups_and_uppercases_type() -> None:
    structured = ExplicitFakeQuestionStructured()
    questions = await question_service(structured).generate(
        provider_id=None,
        skill_id="java-backend",
        difficulty="mid",
        resume_text="",
        question_count=3,
        historical_questions=[],
        custom_categories=None,
        jd_text=None,
    )

    assert len(questions) == 6
    assert [item.question_index for item in questions] == list(range(6))
    assert questions[0].type == "JAVA"
    assert questions[1].is_follow_up is True
    assert questions[1].parent_question_index == 0
    assert structured.calls == [("方向题生成失败：", 3)]


@pytest.mark.asyncio
async def test_explicit_fake_resume_failure_regenerates_all_direction_questions() -> None:
    structured = ExplicitFakeQuestionStructured(fail_resume=True)
    questions = await question_service(structured).generate(
        provider_id=None,
        skill_id="java-backend",
        difficulty="mid",
        resume_text="有项目经历",
        question_count=3,
        historical_questions=[],
        custom_categories=None,
        jd_text=None,
    )

    assert sum(not item.is_follow_up for item in questions) == 3
    assert ("简历题生成失败：", 2) in structured.calls
    assert ("方向题生成失败：", 3) in structured.calls


@pytest.mark.asyncio
async def test_explicit_fake_direction_failure_returns_generated_resume_questions_only() -> None:
    structured = ExplicitFakeQuestionStructured(fail_direction=True)
    questions = await question_service(structured).generate(
        provider_id=None,
        skill_id="java-backend",
        difficulty="mid",
        resume_text="有项目经历",
        question_count=3,
        historical_questions=[],
        custom_categories=None,
        jd_text=None,
    )

    assert sum(not item.is_follow_up for item in questions) == 2
    assert structured.calls.count(("简历题生成失败：", 2)) == 1
    assert structured.calls.count(("方向题生成失败：", 1)) == 1


@pytest.mark.asyncio
async def test_explicit_fake_jd_parse_uses_unified_adapter_and_compatibility_length_rule() -> None:
    skills = InterviewSkillLibrary(SkillRepository(RESOURCES), RESOURCES)
    service = JdParseService(
        cast(Any, ExplicitFakeRegistry()),
        cast(Any, ExplicitFakeJdStructured()),
        PromptRepository(RESOURCES),
        PromptSanitizer(uuid_factory=lambda: uuid.UUID(int=0)),
        skills,
    )
    with pytest.raises(BusinessException, match="JD 内容太少"):
        await service.parse("太短")

    categories = await service.parse("Java 后端工程师，要求熟悉 Spring、MySQL、Redis。" * 3)

    assert [item.model_dump(by_alias=True) for item in categories] == [
        {
            "key": "JAVA",
            "label": "Java",
            "priority": "CORE",
            "ref": "java-core.md",
            "shared": False,
        }
    ]


@pytest.mark.asyncio
async def test_explicit_fake_evaluation_is_sequential_and_zero_fills_failed_batch() -> None:
    structured = ExplicitFakeEvaluationStructured()
    service = UnifiedEvaluationService(
        cast(Any, structured),
        PromptRepository(RESOURCES),
        batch_size=2,
    )
    report = await service.evaluate(
        PROVIDER,
        "session-1",
        [
            QaRecord(0, "问题一", "A", "回答一"),
            QaRecord(1, "问题二", "A", "回答二"),
            QaRecord(2, "问题三", "B", "回答三"),
        ],
        "",
        "",
    )

    assert structured.output_types == [
        BatchReportOutput,
        BatchReportOutput,
        SummaryOutput,
    ]
    assert [item.score for item in report.question_details] == [80, 60, 0]
    assert report.question_details[2].feedback == "该题未成功生成评估结果，系统按 0 分处理。"
    assert report.overall_score == 46
    assert report.overall_feedback == "首批反馈"
    assert report.strengths == ["准确"]
    assert report.improvements == ["深入"]


class ExplicitFakeStreams:
    def __init__(self) -> None:
        self.acks: list[str] = []

    async def ack(self, definition: object, *message_ids: str) -> int:
        del definition
        self.acks.extend(message_ids)
        return len(message_ids)


class ExplicitFailingRetryHandler:
    async def parse(self, message: StreamMessage) -> str | None:
        return message.data.get("sessionId")

    async def should_skip(self, payload: str) -> bool:
        del payload
        return False

    async def try_mark_processing(self, payload: str) -> bool:
        del payload
        return True

    async def process(self, payload: str) -> None:
        del payload
        raise RuntimeError("explicit process failure")

    async def mark_completed(self, payload: str) -> None:
        raise AssertionError(payload)

    async def retry(self, payload: str, retry_count: int) -> None:
        del payload, retry_count
        raise RuntimeError("explicit requeue failure")

    async def mark_failed(self, payload: str, error: str) -> None:
        raise AssertionError((payload, error))


@pytest.mark.asyncio
async def test_requeue_failure_preserves_original_pending_message() -> None:
    streams = ExplicitFakeStreams()
    consumer = SequentialStreamConsumer(
        cast(Any, streams),
        INTERVIEW_EVALUATE,
        "evaluate-consumer-explicit-fake",
        ExplicitFailingRetryHandler(),
    )

    await consumer.process_message(
        StreamMessage(
            message_id="1-0",
            data={"sessionId": "session-1", "retryCount": "0"},
        )
    )

    assert streams.acks == []
