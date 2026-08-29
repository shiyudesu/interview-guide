from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from interview_guide.common.ai.opentrek import OpenTrekCapability, OpenTrekProviderConfig
from interview_guide.common.ai.prompts import PromptRepository, PromptSanitizer
from interview_guide.common.redis.streams import StreamMessage
from interview_guide.modules.knowledge_base.question_models import (
    CreateKnowledgeBaseInterviewRequest,
    CreateKnowledgeBaseQuestionRequest,
    GeneratedQuestion,
    GeneratedQuestionFollowUp,
    GeneratedQuestionList,
    GenerateKnowledgeBaseQuestionsRequest,
    KnowledgeBaseQuestionFollowUp,
)
from interview_guide.modules.knowledge_base.question_service import (
    KnowledgeBaseInterviewService,
    KnowledgeBaseQuestionGenerationService,
    QuestionGenerationRecoveryService,
    QuestionGenStreamHandler,
    parse_follow_ups,
    split_question_generation_context,
)

FIXED_NOW = datetime(2026, 8, 17, 8, 0)


class EmptySessionContext:
    def __call__(self) -> EmptySessionContext:
        return self

    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *args: object) -> None:
        del args


class EmptyQuestionRepository:
    def __init__(self, session: object) -> None:
        del session

    async def categories(self, knowledge_base_id: int) -> list[object]:
        del knowledge_base_id
        return []

    async def recent_questions(self, knowledge_base_id: int, difficulty: str) -> list[object]:
        del knowledge_base_id, difficulty
        return []


class OpenTrekRegistryStub:
    async def get_chat(self, provider_id: str | None = None) -> OpenTrekProviderConfig:
        del provider_id
        return OpenTrekProviderConfig(
            provider_id="opentrek:evaluator",
            base_url="http://10.128.203.200/gateway",
            api_key="key",
            model="agent",
            capability=OpenTrekCapability.EVALUATOR,
        )


class RecordingStructuredInvoker:
    def __init__(self) -> None:
        self.users: list[str] = []

    async def invoke(self, provider: object, system: str, user: str, *args: object) -> Any:
        del provider, system, args
        self.users.append(user)
        index = len(self.users)
        return GeneratedQuestionList(questions=[GeneratedQuestion(question=f"题目 {index}")])


def test_requests_apply_defaults_and_validation_messages() -> None:
    generation = GenerateKnowledgeBaseQuestionsRequest(
        questionCount=2,
        categoryLimit=3,
    )
    assert generation.follow_up_count is None
    assert generation.difficulty is None
    interview = CreateKnowledgeBaseInterviewRequest(
        knowledgeBaseId=1,
        mainQuestionCount=2,
    )
    assert interview.follow_up_count == 0

    with pytest.raises(ValidationError, match="题目难度不合法"):
        GenerateKnowledgeBaseQuestionsRequest(
            difficulty="expert",
            questionCount=2,
            categoryLimit=3,
        )
    with pytest.raises(ValidationError, match="面试方向不能为空"):
        CreateKnowledgeBaseQuestionRequest(
            category=" ",
            question="有效题干",
        )
    with pytest.raises(ValidationError, match="题干不能为空"):
        CreateKnowledgeBaseQuestionRequest(
            category="Redis",
            question=" ",
        )


def test_follow_up_parser_rejects_non_structured_items() -> None:
    value = json.dumps(["非结构化追问"])
    assert parse_follow_ups(value) == []


def test_opentrek_question_context_uses_distinct_markdown_sections() -> None:
    context = (
        "# 资料\n\n## Redis\n" + "缓存穿透治理。" * 20 + "\n\n## PostgreSQL\n" + "事务隔离。" * 20
    )

    batches = split_question_generation_context(context, 2)

    assert len(batches) == 2
    assert "缓存穿透" in batches[0]
    assert "事务隔离" in batches[1]


async def test_opentrek_question_generation_batches_one_question_per_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "interview_guide.modules.knowledge_base.question_service.KnowledgeBaseQuestionRepository",
        EmptyQuestionRepository,
    )
    structured = RecordingStructuredInvoker()
    service = KnowledgeBaseQuestionGenerationService(
        cast(Any, EmptySessionContext()),
        cast(Any, None),
        cast(Any, None),
        cast(Any, structured),
        PromptRepository(Path(__file__).resolve().parents[2] / "resources"),
        PromptSanitizer(),
        cast(Any, None),
    )

    result = await service._call_llm(
        1,
        "知识库",
        "mid",
        3,
        1,
        2,
        None,
        "技术上下文",
        cast(Any, OpenTrekRegistryStub()),
    )

    assert [item.question for item in result.questions or [] if item is not None] == [
        "题目 1",
        "题目 2",
        "题目 3",
    ]
    assert len(structured.users) == 3
    assert all("生成 1 道面试题" in user for user in structured.users)
    assert all("每道主问题配 0 个追问" in user for user in structured.users)


def test_explicit_fake_generation_normalizes_duplicates_and_strict_followup_limit() -> None:
    service = KnowledgeBaseQuestionGenerationService(
        cast(Any, None),
        cast(Any, None),
        cast(Any, None),
        cast(Any, None),
        cast(Any, None),
        cast(Any, None),
        cast(Any, None),
        now=lambda: FIXED_NOW,
    )
    follow_ups = [
        GeneratedQuestionFollowUp(question="追问一"),
        GeneratedQuestionFollowUp(question="追问二"),
    ]
    questions, skipped = service._build_entities(
        1,
        "hash",
        "知识库",
        "mid",
        "固定上下文",
        1,
        [
            GeneratedQuestion(
                category="Redis",
                question="什么是 Redis？",
                followUps=follow_ups,
            ),
            GeneratedQuestion(
                category="Redis",
                question="什么是Redis",
                followUps=follow_ups,
            ),
        ],
    )
    assert len(questions) == 1
    assert skipped == 1
    assert len(json.loads(questions[0].follow_ups_json or "[]")) == 1

    no_follow_ups, _ = service._build_entities(
        1,
        "hash",
        "知识库",
        "mid",
        "固定上下文",
        0,
        [GeneratedQuestion(question="零追问题", followUps=follow_ups)],
    )
    assert json.loads(no_follow_ups[0].follow_ups_json or "[]") == []


class FakeState:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def try_mark_processing(self, knowledge_base_id: int, task_id: str) -> bool:
        self.events.append(f"claim:{knowledge_base_id}:{task_id}")
        return True

    async def get_config(self, knowledge_base_id: int, task_id: str) -> object:
        self.events.append(f"config:{knowledge_base_id}:{task_id}")
        return object()

    async def reset_for_retry(self, knowledge_base_id: int, task_id: str) -> bool:
        self.events.append(f"reset:{knowledge_base_id}:{task_id}")
        return True

    async def mark_failed(self, knowledge_base_id: int, task_id: str) -> bool:
        self.events.append(f"failed:{knowledge_base_id}:{task_id}")
        return True


class FakeProducer:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def send(
        self,
        knowledge_base_id: int,
        task_id: str,
        retry_count: int = 0,
    ) -> bool:
        self.events.append(f"send:{knowledge_base_id}:{task_id}:{retry_count}")
        return True


class FakeGeneration:
    async def execute(
        self,
        knowledge_base_id: int,
        task_id: str,
        config: object,
    ) -> None:
        del knowledge_base_id, task_id, config


@pytest.mark.asyncio
async def test_question_generation_retry_resets_state_before_requeue() -> None:
    state = FakeState()
    handler = QuestionGenStreamHandler(
        cast(Any, state),
        cast(Any, FakeProducer(state.events)),
        cast(Any, FakeGeneration()),
    )
    payload = await handler.parse(
        StreamMessage(
            "1-0",
            {"kbId": "7", "taskId": "task-7", "retryCount": "0"},
        )
    )
    assert payload is not None
    await handler.retry(payload, 1)
    assert state.events == [
        "reset:7:task-7",
        "send:7:task-7:1",
    ]


class FirstRandom:
    def shuffle(self, values: list[Any]) -> None:
        del values

    def randrange(self, start: int, stop: int) -> int:
        del stop
        return start


def test_followup_selection_is_injected_and_strict() -> None:
    service = KnowledgeBaseInterviewService(
        cast(Any, None),
        cast(Any, None),
        random_selection=FirstRandom(),
    )
    pool = [
        KnowledgeBaseQuestionFollowUp(question="追问一"),
        KnowledgeBaseQuestionFollowUp(question="追问二"),
        KnowledgeBaseQuestionFollowUp(question="追问三"),
    ]
    assert [item.question for item in service._pick_follow_ups(pool, 2)] == [
        "追问一",
        "追问二",
    ]


class RecoveryState:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def stale_tasks(
        self,
        status: object,
        threshold: datetime,
    ) -> list[tuple[int, str]]:
        self.events.append(f"stale:{status}:{threshold.isoformat()}")
        return [(1, f"{status}-task")]

    async def touch_queued_for_recovery(
        self,
        knowledge_base_id: int,
        task_id: str,
        threshold: datetime,
    ) -> bool:
        del threshold
        self.events.append(f"touch:{knowledge_base_id}:{task_id}")
        return True

    async def reset_stale_processing(
        self,
        knowledge_base_id: int,
        task_id: str,
        threshold: datetime,
    ) -> bool:
        del threshold
        self.events.append(f"reset:{knowledge_base_id}:{task_id}")
        return True


@pytest.mark.asyncio
async def test_scheduler_requeues_queued_and_processing_tasks() -> None:
    state = RecoveryState()
    recovery = QuestionGenerationRecoveryService(
        cast(Any, state),
        cast(Any, FakeProducer(state.events)),
        now=lambda: FIXED_NOW,
    )
    await recovery.recover()
    assert any(event.startswith("touch:1:QUEUED-task") for event in state.events)
    assert any(event.startswith("reset:1:PROCESSING-task") for event in state.events)
    assert "send:1:QUEUED-task:0" in state.events
    assert "send:1:PROCESSING-task:0" in state.events
