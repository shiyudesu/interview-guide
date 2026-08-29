from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from interview_guide.common.ai.adapter import ChatResult, ProviderConfig
from interview_guide.common.ai.prompts import ANTI_INJECTION_INSTRUCTION, PromptRepository
from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.modules.knowledge_base.models import QueryRequest, QueryResponse
from interview_guide.modules.knowledge_base.repository import (
    VectorSearchHit,
)
from interview_guide.modules.knowledge_base.vectorization import EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)
NO_RESULT_RESPONSE = (
    "抱歉，在选定的知识库中未检索到相关信息。请换一个更具体的关键词或补充上下文后再试。"
)
STREAM_ERROR_RESPONSE = "【错误】知识库查询失败：AI服务暂时不可用，请稍后重试。"
STREAM_PROBE_CHARS = 120
MAX_REWRITE_HISTORY_CHARS = 200
MEDIUM_QUERY_LENGTH = 12
WHITESPACE = re.compile(r"[ \t\n\x0b\f\r]+")
NO_RESULT_MARKERS = (
    "没有找到相关信息",
    "未检索到相关信息",
    "信息不足",
    "超出知识库范围",
    "无法根据提供内容回答",
)


class QueryProviderRegistry(Protocol):
    async def get_chat(self, provider_id: str | None = None) -> ProviderConfig: ...

    async def get_embedding(
        self,
        provider_id: str | None = None,
    ) -> ProviderConfig: ...


class QueryRepository(Protocol):
    async def increment_question_counts(
        self,
        knowledge_base_ids: Sequence[int],
    ) -> None: ...

    async def knowledge_base_names(
        self,
        knowledge_base_ids: Sequence[int],
    ) -> list[str]: ...

    async def similarity_search(
        self,
        knowledge_base_ids: Sequence[int],
        embedding: Sequence[float],
        top_k: int,
        min_score: float,
    ) -> list[VectorSearchHit]: ...

    async def similarity_search_unfiltered(
        self,
        embedding: Sequence[float],
        top_k: int,
        min_score: float,
    ) -> list[VectorSearchHit]: ...


class QueryLlmAdapter(Protocol):
    async def chat(
        self,
        provider: ProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> ChatResult: ...

    def stream_chat(
        self,
        provider: ProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]: ...

    async def embed(
        self,
        provider: ProviderConfig,
        inputs: Sequence[str],
    ) -> list[list[float]]: ...


class QueryRetriever(Protocol):
    async def retrieve(
        self,
        knowledge_base_ids: Sequence[int],
        query: str,
        top_k: int,
        min_score: float,
    ) -> list[VectorSearchHit]: ...


@dataclass(frozen=True)
class QueryConfiguration:
    rewrite_enabled: bool = True
    short_query_length: int = 4
    topk_short: int = 20
    topk_medium: int = 12
    topk_long: int = 8
    min_score_short: float = 0.18
    min_score_default: float = 0.28

    @classmethod
    def from_settings(cls, settings: Settings) -> QueryConfiguration:
        return cls(
            rewrite_enabled=settings.ai_rag_rewrite_enabled,
            short_query_length=settings.ai_rag_short_query_length,
            topk_short=settings.ai_rag_topk_short,
            topk_medium=settings.ai_rag_topk_medium,
            topk_long=settings.ai_rag_topk_long,
            min_score_short=settings.ai_rag_min_score_short,
            min_score_default=settings.ai_rag_min_score_default,
        )


@dataclass(frozen=True)
class SearchParameters:
    top_k: int
    min_score: float


@dataclass(frozen=True)
class QueryContext:
    original_question: str
    candidate_queries: tuple[str, ...]
    search: SearchParameters


class KnowledgeBaseQueryService:
    def __init__(
        self,
        repository: QueryRepository,
        registry: QueryProviderRegistry,
        adapter: QueryLlmAdapter,
        prompts: PromptRepository,
        configuration: QueryConfiguration,
        tools: Sequence[dict[str, Any]] = (),
        retriever: QueryRetriever | None = None,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._adapter = adapter
        self._prompts = prompts
        self._configuration = configuration
        self._tools = list(tools)
        self._retriever = retriever

    async def query(self, request: QueryRequest) -> QueryResponse:
        answer = await self.answer_question(
            request.knowledge_base_ids,
            request.question,
        )
        knowledge_base_ids = self._validated_ids(request.knowledge_base_ids)
        names = await self._repository.knowledge_base_names(knowledge_base_ids)
        return QueryResponse(
            answer=answer,
            knowledge_base_id=request.knowledge_base_ids[0],
            knowledge_base_name="、".join(names),
        )

    async def answer_question(
        self,
        knowledge_base_ids: Sequence[int | None] | None,
        question: str | None,
    ) -> str:
        normalized_question = self._normalize_question(question)
        if not knowledge_base_ids or not normalized_question:
            return NO_RESULT_RESPONSE

        validated_ids = self._validated_ids(knowledge_base_ids)
        await self._repository.increment_question_counts(validated_ids)
        context = await self._build_query_context(normalized_question)
        relevant_documents = await self._retrieve_relevant_documents(
            context,
            validated_ids,
        )
        if not relevant_documents:
            return NO_RESULT_RESPONSE

        try:
            provider = await self._registry.get_chat()
            result = await self._adapter.chat(
                provider,
                self._answer_messages(relevant_documents, normalized_question),
                tools=self._tools or None,
            )
            return self._normalize_answer(result.content)
        except Exception as error:
            logger.exception(
                "knowledge base answer failed kbIds=%s",
                knowledge_base_ids,
            )
            raise BusinessException(
                ErrorCode.KNOWLEDGE_BASE_QUERY_FAILED,
                f"知识库查询失败：{error}",
            ) from error

    async def answer_question_stream(
        self,
        knowledge_base_ids: Sequence[int | None] | None,
        question: str | None,
        history: Sequence[dict[str, str]] | None = None,
    ) -> AsyncIterator[str]:
        normalized_question = self._normalize_question(question)
        if not knowledge_base_ids or not normalized_question:
            return self._single_chunk(NO_RESULT_RESPONSE)

        try:
            validated_ids = self._validated_ids(knowledge_base_ids)
            await self._repository.increment_question_counts(validated_ids)
            effective_history = list(history or ())
            context = await self._build_query_context(
                normalized_question,
                effective_history,
            )
            relevant_documents = await self._retrieve_relevant_documents(
                context,
                validated_ids,
            )
            if not relevant_documents:
                return self._single_chunk(NO_RESULT_RESPONSE)
            provider = await self._registry.get_chat()
            raw_stream = self._content_stream(
                self._adapter.stream_chat(
                    provider,
                    self._answer_messages(
                        relevant_documents,
                        normalized_question,
                        effective_history,
                    ),
                    tools=self._tools or None,
                )
            )
            return self._normalize_stream(raw_stream)
        except Exception as error:
            logger.exception(
                "knowledge base stream preparation failed kbIds=%s",
                knowledge_base_ids,
            )
            return self._single_chunk(f"【错误】知识库查询失败：{error}")

    async def _build_query_context(
        self,
        normalized_question: str,
        history: Sequence[dict[str, str]] = (),
    ) -> QueryContext:
        rewritten_question = await self._rewrite_question(
            normalized_question,
            history,
        )
        candidates = tuple(dict.fromkeys((rewritten_question, normalized_question)))
        return QueryContext(
            original_question=normalized_question,
            candidate_queries=candidates,
            search=self._resolve_search_parameters(normalized_question),
        )

    async def _rewrite_question(
        self,
        question: str,
        history: Sequence[dict[str, str]] = (),
    ) -> str:
        if not self._configuration.rewrite_enabled or not question:
            return question
        try:
            provider = await self._registry.get_chat()
            prompt = self._prompts.render(
                "knowledgebase-query-rewrite.st",
                {
                    "question": question,
                    "history": self._format_history_for_rewrite(history),
                },
            )
            prompt = prompt.rstrip("\n") + "\n"
            result = await self._adapter.chat(
                provider,
                [{"role": "user", "content": prompt}],
                tools=self._tools or None,
            )
            rewritten = (result.content or "").strip()
            return rewritten or question
        except Exception:
            logger.warning(
                "knowledge base query rewrite failed; using original question",
                exc_info=True,
            )
            return question

    async def _retrieve_relevant_documents(
        self,
        context: QueryContext,
        knowledge_base_ids: Sequence[int],
    ) -> list[VectorSearchHit]:
        if self._retriever is not None:
            for candidate in context.candidate_queries:
                if not candidate:
                    continue
                documents = await self._retriever.retrieve(
                    knowledge_base_ids,
                    candidate,
                    context.search.top_k,
                    context.search.min_score,
                )
                if documents:
                    return documents
            return []
        for candidate in context.candidate_queries:
            if not candidate:
                continue
            try:
                embedding = await self._embed_query(candidate)
                documents = await self._repository.similarity_search(
                    knowledge_base_ids,
                    embedding,
                    context.search.top_k,
                    context.search.min_score,
                )
            except Exception:
                logger.warning(
                    "knowledge base vector prefilter failed; using local fallback",
                    exc_info=True,
                )
                try:
                    embedding = await self._embed_query(candidate)
                    fallback = await self._repository.similarity_search_unfiltered(
                        embedding,
                        max(context.search.top_k * 3, context.search.top_k),
                        context.search.min_score,
                    )
                    allowed_ids = set(knowledge_base_ids)
                    documents = [
                        document
                        for document in fallback
                        if document.knowledge_base_id in allowed_ids
                    ][: context.search.top_k]
                except Exception as error:
                    logger.exception("knowledge base vector search failed")
                    raise BusinessException(
                        ErrorCode.KNOWLEDGE_BASE_QUERY_FAILED,
                        f"向量搜索失败: {error}",
                    ) from error
            if documents:
                return documents
        return []

    async def _embed_query(self, query: str) -> list[float]:
        provider = await self._registry.get_embedding()
        if provider.embedding_dimensions != EMBEDDING_DIMENSIONS:
            raise ValueError(
                "Embedding dimension must be "
                f"{EMBEDDING_DIMENSIONS}, got {provider.embedding_dimensions}"
            )
        embeddings = await self._adapter.embed(provider, [query])
        if len(embeddings) != 1 or len(embeddings[0]) != EMBEDDING_DIMENSIONS:
            actual = len(embeddings[0]) if embeddings else 0
            raise ValueError(
                f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSIONS}, got {actual}"
            )
        return embeddings[0]

    def _answer_messages(
        self,
        documents: Sequence[VectorSearchHit],
        question: str,
        history: Sequence[dict[str, str]] = (),
    ) -> list[dict[str, str]]:
        context = "\n\n---\n\n".join(document.content for document in documents)
        system_prompt = (
            self._prompts.render("knowledgebase-query-system.st") + ANTI_INJECTION_INSTRUCTION
        )
        user_prompt = self._prompts.render(
            "knowledgebase-query-user.st",
            {"context": context, "question": question},
        )
        return [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": user_prompt},
        ]

    @staticmethod
    def _format_history_for_rewrite(
        history: Sequence[dict[str, str]],
    ) -> str:
        lines: list[str] = []
        for message in history:
            role = message.get("role")
            content = message.get("content", "")
            if role == "user":
                lines.append(f"用户: {content}")
            elif role == "assistant":
                if len(content) > MAX_REWRITE_HISTORY_CHARS:
                    content = content[:MAX_REWRITE_HISTORY_CHARS] + "..."
                lines.append(f"助手: {content}")
        return "\n".join(lines).strip()

    def _resolve_search_parameters(self, question: str) -> SearchParameters:
        compact_length = len(WHITESPACE.sub("", question))
        if compact_length <= self._configuration.short_query_length:
            return SearchParameters(
                max(self._configuration.topk_short, 1),
                self._configuration.min_score_short,
            )
        if compact_length <= MEDIUM_QUERY_LENGTH:
            return SearchParameters(
                max(self._configuration.topk_medium, 1),
                self._configuration.min_score_default,
            )
        return SearchParameters(
            max(self._configuration.topk_long, 1),
            self._configuration.min_score_default,
        )

    @staticmethod
    def _normalize_question(question: str | None) -> str:
        return question.strip() if question is not None else ""

    @staticmethod
    def _validated_ids(
        knowledge_base_ids: Sequence[int | None],
    ) -> list[int]:
        for knowledge_base_id in knowledge_base_ids:
            if knowledge_base_id is None:
                raise BusinessException(
                    ErrorCode.NOT_FOUND,
                    "知识库不存在: null",
                )
        return [
            knowledge_base_id
            for knowledge_base_id in knowledge_base_ids
            if knowledge_base_id is not None
        ]

    @staticmethod
    def _normalize_answer(answer: str | None) -> str:
        if answer is None or not answer.strip():
            return NO_RESULT_RESPONSE
        normalized = answer.strip()
        if any(marker in normalized for marker in NO_RESULT_MARKERS):
            return NO_RESULT_RESPONSE
        return normalized

    @staticmethod
    async def _single_chunk(content: str) -> AsyncIterator[str]:
        yield content

    @staticmethod
    async def _content_stream(
        events: AsyncIterator[dict[str, Any]],
    ) -> AsyncIterator[str]:
        try:
            async for event in events:
                choices = event.get("choices")
                if not isinstance(choices, list) or not choices:
                    continue
                choice = choices[0]
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta")
                if not isinstance(delta, dict):
                    continue
                content = delta.get("content")
                if isinstance(content, str):
                    yield content
        finally:
            close = getattr(events, "aclose", None)
            if close is not None:
                await close()

    async def _normalize_stream(
        self,
        raw_stream: AsyncIterator[str],
    ) -> AsyncIterator[str]:
        probe_buffer = ""
        passthrough = False
        try:
            async for chunk in raw_stream:
                if passthrough:
                    yield chunk
                    continue
                probe_buffer += chunk
                if any(marker in probe_buffer for marker in NO_RESULT_MARKERS):
                    yield NO_RESULT_RESPONSE
                    return
                if len(probe_buffer) >= STREAM_PROBE_CHARS:
                    passthrough = True
                    yield probe_buffer
                    probe_buffer = ""
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("knowledge base model stream failed")
            yield STREAM_ERROR_RESPONSE
            return
        finally:
            close = getattr(raw_stream, "aclose", None)
            if close is not None:
                await close()
        if not passthrough:
            yield self._normalize_answer(probe_buffer)
