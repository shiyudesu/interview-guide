from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from interview_guide.common.ai.adapter import ChatResult, ProviderConfig
from interview_guide.common.ai.prompts import PromptRepository
from interview_guide.common.errors import BusinessException
from interview_guide.modules.knowledge_base.api import sse_data
from interview_guide.modules.knowledge_base.models import QueryRequest
from interview_guide.modules.knowledge_base.query_service import (
    NO_RESULT_RESPONSE,
    STREAM_ERROR_RESPONSE,
    KnowledgeBaseQueryService,
    QueryConfiguration,
)
from interview_guide.modules.knowledge_base.repository import VectorSearchHit
from interview_guide.modules.knowledge_base.vectorization import EMBEDDING_DIMENSIONS

RESOURCES = Path(__file__).resolve().parents[2] / "resources"


def provider(provider_id: str) -> ProviderConfig:
    return ProviderConfig(
        provider_id=provider_id,
        base_url="https://fake.invalid",
        api_key="explicit-fake-key",
        model="explicit-fake-chat",
        embedding_model="explicit-fake-embedding",
        embedding_dimensions=EMBEDDING_DIMENSIONS,
        supports_embedding=True,
    )


@dataclass
class ExplicitFakeQueryRepository:
    search_results: list[list[VectorSearchHit]]
    fallback_results: list[list[VectorSearchHit]] = field(default_factory=list)
    names: dict[int, str] = field(default_factory=lambda: {1: "第一库", 2: "第二库"})
    increment_calls: list[list[int]] = field(default_factory=list)
    searches: list[tuple[list[int], list[float], int, float]] = field(default_factory=list)

    async def increment_question_counts(
        self,
        knowledge_base_ids: Sequence[int],
    ) -> None:
        self.increment_calls.append(list(knowledge_base_ids))

    async def knowledge_base_names(
        self,
        knowledge_base_ids: Sequence[int],
    ) -> list[str]:
        return [self.names[value] for value in knowledge_base_ids]

    async def similarity_search(
        self,
        knowledge_base_ids: Sequence[int],
        embedding: Sequence[float],
        top_k: int,
        min_score: float,
    ) -> list[VectorSearchHit]:
        self.searches.append((list(knowledge_base_ids), list(embedding), top_k, min_score))
        return self.search_results.pop(0)

    async def similarity_search_unfiltered(
        self,
        embedding: Sequence[float],
        top_k: int,
        min_score: float,
    ) -> list[VectorSearchHit]:
        self.searches.append(([], list(embedding), top_k, min_score))
        return self.fallback_results.pop(0)


@dataclass
class ExplicitFakeRegistry:
    chat: ProviderConfig = field(default_factory=lambda: provider("fake-chat"))
    embedding: ProviderConfig = field(default_factory=lambda: provider("fake-embedding"))

    async def get_chat(self, provider_id: str | None = None) -> ProviderConfig:
        del provider_id
        return self.chat

    async def get_embedding(
        self,
        provider_id: str | None = None,
    ) -> ProviderConfig:
        del provider_id
        return self.embedding


class ExplicitFakeLlmAdapter:
    def __init__(
        self,
        *,
        chat_contents: list[str | None],
        stream_chunks: list[str] | None = None,
        stream_error: Exception | None = None,
    ) -> None:
        self.chat_contents = chat_contents
        self.stream_chunks = stream_chunks or []
        self.stream_error = stream_error
        self.chat_messages: list[list[dict[str, Any]]] = []
        self.embedding_inputs: list[list[str]] = []
        self.stream_closed = False

    async def chat(
        self,
        provider_config: ProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        del provider_config, tools, tool_choice, temperature
        self.chat_messages.append(list(messages))
        content = self.chat_contents.pop(0)
        return ChatResult(
            content=content,
            message={"role": "assistant", "content": content},
            usage=None,
            raw={},
        )

    async def stream_chat(
        self,
        provider_config: ProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        del provider_config, tools, tool_choice, temperature
        self.chat_messages.append(list(messages))
        try:
            for chunk in self.stream_chunks:
                yield {"choices": [{"delta": {"content": chunk}}]}
            if self.stream_error is not None:
                raise self.stream_error
        finally:
            self.stream_closed = True

    async def embed(
        self,
        provider_config: ProviderConfig,
        inputs: Sequence[str],
    ) -> list[list[float]]:
        del provider_config
        self.embedding_inputs.append(list(inputs))
        marker = float(len(self.embedding_inputs))
        return [[marker] + [0.0] * (EMBEDDING_DIMENSIONS - 1)]


class RewriteFailingExplicitFakeAdapter(ExplicitFakeLlmAdapter):
    def __init__(self) -> None:
        super().__init__(chat_contents=["固定回答"])
        self.failed_rewrite = False

    async def chat(
        self,
        provider_config: ProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        if not self.failed_rewrite:
            self.failed_rewrite = True
            raise RuntimeError("explicit fake rewrite failure")
        return await super().chat(
            provider_config,
            messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
        )


class EmbeddingFailingExplicitFakeAdapter(ExplicitFakeLlmAdapter):
    def __init__(self) -> None:
        super().__init__(chat_contents=[])
        self.embedding_attempts = 0

    async def embed(
        self,
        provider_config: ProviderConfig,
        inputs: Sequence[str],
    ) -> list[list[float]]:
        del provider_config, inputs
        self.embedding_attempts += 1
        raise RuntimeError("explicit fake embedding failure")


def query_service(
    repository: ExplicitFakeQueryRepository,
    adapter: ExplicitFakeLlmAdapter,
    *,
    rewrite_enabled: bool,
) -> KnowledgeBaseQueryService:
    return KnowledgeBaseQueryService(
        repository,
        ExplicitFakeRegistry(),
        adapter,
        PromptRepository(RESOURCES),
        QueryConfiguration(rewrite_enabled=rewrite_enabled),
    )


def test_query_request_uses_java_validation_messages() -> None:
    with pytest.raises(ValidationError, match="至少选择一个知识库"):
        QueryRequest.model_validate({"knowledgeBaseIds": [], "question": "问题"})
    with pytest.raises(ValidationError, match="问题不能为空"):
        QueryRequest.model_validate({"knowledgeBaseIds": [1], "question": " \t"})
    assert (
        QueryRequest.model_validate({"knowledgeBaseIds": [1], "question": "\u00a0"}).question
        == "\u00a0"
    )


@pytest.mark.asyncio
async def test_explicit_fake_query_rewrites_then_falls_back_to_original() -> None:
    repository = ExplicitFakeQueryRepository(
        search_results=[
            [],
            [VectorSearchHit("固定原文", 0.9)],
        ]
    )
    adapter = ExplicitFakeLlmAdapter(
        chat_contents=["改写后的问题", "固定回答"],
    )
    service = query_service(repository, adapter, rewrite_enabled=True)

    result = await service.query(QueryRequest(knowledgeBaseIds=[1, 2, 1], question="原始问题"))

    assert result.answer == "固定回答"
    assert result.knowledge_base_id == 1
    assert result.knowledge_base_name == "第一库、第二库、第一库"
    assert repository.increment_calls == [[1, 2, 1]]
    assert adapter.embedding_inputs == [["改写后的问题"], ["原始问题"]]
    assert [search[2:] for search in repository.searches] == [
        (20, 0.18),
        (20, 0.18),
    ]
    assert "固定原文" in adapter.chat_messages[-1][1]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "top_k", "min_score"),
    [
        ("短问", 20, 0.18),
        ("这是一个中等问题", 12, 0.28),
        ("这是一个明显超过十二个字符的长问题", 8, 0.28),
    ],
)
async def test_explicit_fake_dynamic_search_parameters(
    question: str,
    top_k: int,
    min_score: float,
) -> None:
    repository = ExplicitFakeQueryRepository(search_results=[[VectorSearchHit("固定原文", 1.0)]])
    adapter = ExplicitFakeLlmAdapter(chat_contents=["固定回答"])
    service = query_service(repository, adapter, rewrite_enabled=False)

    await service.answer_question([1], question)

    assert repository.searches[0][2:] == (top_k, min_score)


@pytest.mark.asyncio
async def test_explicit_fake_rewrite_failure_uses_original_question() -> None:
    repository = ExplicitFakeQueryRepository(search_results=[[VectorSearchHit("固定原文", 1.0)]])
    adapter = RewriteFailingExplicitFakeAdapter()
    service = query_service(repository, adapter, rewrite_enabled=True)

    assert await service.answer_question([1], "原始问题") == "固定回答"
    assert adapter.embedding_inputs == [["原始问题"]]


@pytest.mark.asyncio
async def test_explicit_fake_vector_prefilter_falls_back_to_local_filter() -> None:
    repository = ExplicitFakeQueryRepository(
        search_results=[],
        fallback_results=[
            [
                VectorSearchHit("其他库", 1.0, 2),
                VectorSearchHit("目标库", 0.9, 1),
            ]
        ],
    )
    adapter = ExplicitFakeLlmAdapter(chat_contents=["固定回答"])
    service = query_service(repository, adapter, rewrite_enabled=False)

    assert await service.answer_question([1], "问题") == "固定回答"
    assert repository.searches[0][2:] == (20, 0.18)
    assert repository.searches[1][2:] == (60, 0.18)


@pytest.mark.asyncio
async def test_explicit_fake_vector_failure_retries_once_then_maps_error() -> None:
    repository = ExplicitFakeQueryRepository(search_results=[])
    adapter = EmbeddingFailingExplicitFakeAdapter()
    service = query_service(repository, adapter, rewrite_enabled=False)

    with pytest.raises(BusinessException, match="向量搜索失败"):
        await service.answer_question([1], "问题")

    assert adapter.embedding_attempts == 2


@pytest.mark.asyncio
async def test_explicit_fake_no_hit_and_no_result_answer_are_normalized() -> None:
    no_hit_repository = ExplicitFakeQueryRepository(search_results=[[]])
    no_hit_adapter = ExplicitFakeLlmAdapter(chat_contents=[])
    no_hit_service = query_service(
        no_hit_repository,
        no_hit_adapter,
        rewrite_enabled=False,
    )

    assert await no_hit_service.answer_question([1], "问题") == NO_RESULT_RESPONSE

    weak_repository = ExplicitFakeQueryRepository(
        search_results=[[VectorSearchHit("固定原文", 1.0)]]
    )
    weak_adapter = ExplicitFakeLlmAdapter(chat_contents=["根据知识库信息不足，无法回答。"])
    weak_service = query_service(
        weak_repository,
        weak_adapter,
        rewrite_enabled=False,
    )

    assert await weak_service.answer_question([1], "问题") == NO_RESULT_RESPONSE


@pytest.mark.asyncio
async def test_null_knowledge_base_id_reaches_java_compatible_business_error() -> None:
    repository = ExplicitFakeQueryRepository(search_results=[])
    adapter = ExplicitFakeLlmAdapter(chat_contents=[])
    service = query_service(repository, adapter, rewrite_enabled=False)

    with pytest.raises(BusinessException, match="知识库不存在: null"):
        await service.answer_question([None], "问题")

    stream = await service.answer_question_stream([None], "问题")
    assert [chunk async for chunk in stream] == ["【错误】知识库查询失败：知识库不存在: null"]


@pytest.mark.asyncio
async def test_explicit_fake_stream_preserves_chunks_and_maps_model_error() -> None:
    repository = ExplicitFakeQueryRepository(search_results=[[VectorSearchHit("固定原文", 1.0)]])
    adapter = ExplicitFakeLlmAdapter(
        chat_contents=[],
        stream_chunks=["甲" * 120, "\n第二段"],
        stream_error=RuntimeError("explicit fake stream failure"),
    )
    service = query_service(repository, adapter, rewrite_enabled=False)

    stream = await service.answer_question_stream([1], "问题")
    chunks = [chunk async for chunk in stream]

    assert chunks == ["甲" * 120, "\n第二段", STREAM_ERROR_RESPONSE]
    assert adapter.stream_closed is True


@pytest.mark.asyncio
async def test_explicit_fake_stream_discards_probe_on_error_and_normalizes_no_result() -> None:
    error_repository = ExplicitFakeQueryRepository(
        search_results=[[VectorSearchHit("固定原文", 1.0)]]
    )
    error_adapter = ExplicitFakeLlmAdapter(
        chat_contents=[],
        stream_chunks=["未达到探测窗口"],
        stream_error=RuntimeError("explicit fake stream failure"),
    )
    error_service = query_service(
        error_repository,
        error_adapter,
        rewrite_enabled=False,
    )

    error_stream = await error_service.answer_question_stream([1], "问题")
    assert [chunk async for chunk in error_stream] == [STREAM_ERROR_RESPONSE]

    no_result_repository = ExplicitFakeQueryRepository(
        search_results=[[VectorSearchHit("固定原文", 1.0)]]
    )
    no_result_adapter = ExplicitFakeLlmAdapter(
        chat_contents=[],
        stream_chunks=["根据内容信息不足，无法回答。", "不应输出"],
    )
    no_result_service = query_service(
        no_result_repository,
        no_result_adapter,
        rewrite_enabled=False,
    )

    no_result_stream = await no_result_service.answer_question_stream([1], "问题")
    assert [chunk async for chunk in no_result_stream] == [NO_RESULT_RESPONSE]
    assert no_result_adapter.stream_closed is True


@pytest.mark.asyncio
async def test_explicit_fake_stream_cancel_closes_upstream_without_extra_output() -> None:
    repository = ExplicitFakeQueryRepository(search_results=[[VectorSearchHit("固定原文", 1.0)]])
    adapter = ExplicitFakeLlmAdapter(
        chat_contents=[],
        stream_chunks=["甲" * 120, "不应读取"],
    )
    service = query_service(repository, adapter, rewrite_enabled=False)

    stream = await service.answer_question_stream([1], "问题")
    assert await anext(stream) == "甲" * 120
    await stream.aclose()

    assert adapter.stream_closed is True


@pytest.mark.asyncio
async def test_explicit_fake_rag_history_is_used_for_rewrite_and_answer() -> None:
    repository = ExplicitFakeQueryRepository(search_results=[[VectorSearchHit("固定原文", 1.0)]])
    adapter = ExplicitFakeLlmAdapter(
        chat_contents=["改写后的问题"],
        stream_chunks=["固定流式回答"],
    )
    service = query_service(repository, adapter, rewrite_enabled=True)
    history = [
        {"role": "user", "content": "上一问"},
        {"role": "assistant", "content": "上一答"},
    ]

    stream = await service.answer_question_stream([1], "追问", history)
    assert [chunk async for chunk in stream] == ["固定流式回答"]

    assert "用户: 上一问" in adapter.chat_messages[0][0]["content"]
    assert "助手: 上一答" in adapter.chat_messages[0][0]["content"]
    assert [message["role"] for message in adapter.chat_messages[1]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert adapter.chat_messages[1][1:3] == history


def test_rag_history_truncates_by_java_utf16_units() -> None:
    formatted = KnowledgeBaseQueryService._format_history_for_rewrite(
        [{"role": "assistant", "content": "😀" * 101}]
    )

    assert formatted == f"助手: {'😀' * 100}..."


def test_sse_data_matches_spring_string_event_framing() -> None:
    assert sse_data("第一行\r\n第二行\n") == (
        b"data:\xe7\xac\xac\xe4\xb8\x80\xe8\xa1\x8c\n"
        b"data:\xe7\xac\xac\xe4\xba\x8c\xe8\xa1\x8c\n"
        b"data:\n\n"
    )
