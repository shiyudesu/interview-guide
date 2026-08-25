from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import tiktoken
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.db.models import KnowledgeBase, VectorStore
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.redis.streams import (
    FIELD_CONTENT,
    FIELD_KB_ID,
    FIELD_RETRY_COUNT,
    KB_VECTORIZE,
    RedisStreamService,
    StreamMessage,
)

logger = logging.getLogger(__name__)

MAX_EMBEDDING_BATCH_SIZE = 10
EMBEDDING_DIMENSIONS = 1024
DEFAULT_CHUNK_SIZE = 800
MIN_CHUNK_SIZE_CHARACTERS = 350
MIN_CHUNK_LENGTH_TO_EMBED = 5
MAX_NUM_CHUNKS = 10_000
PUNCTUATION_MARKS = (".", "?", "!", "\n")


@dataclass(frozen=True)
class PendingVector:
    content: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class EmbeddedVector:
    content: str
    metadata: dict[str, str]
    embedding: list[float]


@dataclass(frozen=True)
class VectorizePayload:
    knowledge_base_id: int
    content: str


class EmbeddingProviderRegistry(Protocol):
    async def get_embedding(
        self,
        provider_id: str | None = None,
    ) -> ProviderConfig: ...


class EmbeddingLlmAdapter(Protocol):
    async def embed(
        self,
        provider: ProviderConfig,
        inputs: Sequence[str],
    ) -> list[list[float]]: ...


class VectorizationRepository(Protocol):
    async def provider_context(
        self,
        knowledge_base_id: int,
    ) -> tuple[uuid.UUID, str] | None: ...

    async def store_pending_batch(
        self,
        vectors: Sequence[EmbeddedVector],
    ) -> None: ...

    async def complete_job(
        self,
        knowledge_base_id: int,
        job_id: str,
        chunk_count: int,
    ) -> bool: ...

    async def cleanup_job(self, job_id: str) -> None: ...


@lru_cache(maxsize=1)
def cl100k_encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def last_punctuation_index(value: str) -> int:
    result = -1
    for punctuation in PUNCTUATION_MARKS:
        index = value.rfind(punctuation)
        if index >= 0:
            result = max(result, index)
    return result


def split_text(
    content: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    min_chunk_size_characters: int = MIN_CHUNK_SIZE_CHARACTERS,
    min_chunk_length_to_embed: int = MIN_CHUNK_LENGTH_TO_EMBED,
    max_num_chunks: int = MAX_NUM_CHUNKS,
) -> list[str]:
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")
    if not content.strip():
        return []
    encoding = cl100k_encoding()
    tokens = encoding.encode(content, disallowed_special=())
    chunks: list[str] = []
    chunk_count = 0
    while tokens and chunk_count < max_num_chunks:
        chunk_tokens = tokens[: min(chunk_size, len(tokens))]
        chunk_text = encoding.decode(chunk_tokens)
        if not chunk_text.strip():
            tokens = tokens[len(chunk_tokens) :]
            continue
        if len(tokens) > chunk_size:
            punctuation_index = last_punctuation_index(chunk_text)
            if punctuation_index != -1 and punctuation_index > min_chunk_size_characters:
                chunk_text = chunk_text[: punctuation_index + 1]
        value = chunk_text.strip()
        if len(value) > min_chunk_length_to_embed:
            chunks.append(value)
        consumed = len(encoding.encode(chunk_text, disallowed_special=()))
        if consumed < 1:
            raise ValueError("token splitter made no progress")
        tokens = tokens[consumed:]
        chunk_count += 1
    if tokens:
        remaining = encoding.decode(tokens).replace(os.linesep, " ").strip()
        if len(remaining) > min_chunk_length_to_embed:
            chunks.append(remaining)
    return chunks


def pending_vectors(
    knowledge_base_id: int,
    job_id: str,
    chunks: Iterable[str],
) -> list[PendingVector]:
    return [
        PendingVector(
            content=chunk,
            metadata={
                "kb_id": f"pending:{knowledge_base_id}:{job_id}",
                "kb_target_id": str(knowledge_base_id),
                "kb_vector_job_id": job_id,
            },
        )
        for chunk in chunks
    ]


def embedding_batches[T](values: list[T]) -> list[list[T]]:
    return [
        values[index : index + MAX_EMBEDDING_BATCH_SIZE]
        for index in range(0, len(values), MAX_EMBEDDING_BATCH_SIZE)
    ]


async def promote_vector_job(
    session: AsyncSession,
    knowledge_base_id: int,
    job_id: str,
) -> None:
    await session.execute(
        text(
            """
            DELETE FROM vector_store
            WHERE metadata->>'kb_id' = :target
            """
        ),
        {"target": str(knowledge_base_id)},
    )
    await session.execute(
        text(
            """
            UPDATE vector_store
            SET metadata = (
                jsonb_set(
                    metadata::jsonb,
                    '{kb_id}',
                    to_jsonb(CAST(:target AS text)),
                    true
                ) - 'kb_vector_job_id' - 'kb_target_id'
            )::json
            WHERE metadata->>'kb_vector_job_id' = :job_id
            """
        ),
        {
            "target": str(knowledge_base_id),
            "job_id": job_id,
        },
    )


class KnowledgeBaseVectorRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def is_missing_or_completed(self, knowledge_base_id: int) -> bool:
        async with self._sessions() as session:
            entity = await session.get(KnowledgeBase, knowledge_base_id)
            return entity is None or entity.vector_status == "COMPLETED"

    async def provider_context(
        self,
        knowledge_base_id: int,
    ) -> tuple[uuid.UUID, str] | None:
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(
                        KnowledgeBase.user_id,
                        KnowledgeBase.embedding_provider_alias,
                    ).where(KnowledgeBase.id == knowledge_base_id)
                )
            ).one_or_none()
            return (row.user_id, row.embedding_provider_alias) if row is not None else None

    async def exists(self, knowledge_base_id: int) -> bool:
        async with self._sessions() as session:
            return await session.get(KnowledgeBase, knowledge_base_id) is not None

    async def update_status(
        self,
        knowledge_base_id: int,
        status: str,
        error: str | None,
    ) -> bool:
        async with self._sessions() as session, session.begin():
            entity = await session.get(KnowledgeBase, knowledge_base_id)
            if entity is None:
                return False
            entity.vector_status = status
            entity.vector_error = error
            return True

    async def store_pending_batch(self, vectors: Sequence[EmbeddedVector]) -> None:
        async with self._sessions() as session, session.begin():
            session.add_all(
                [
                    VectorStore(
                        content=vector.content,
                        metadata_json=vector.metadata,
                        embedding=vector.embedding,
                    )
                    for vector in vectors
                ]
            )

    async def complete_job(
        self,
        knowledge_base_id: int,
        job_id: str,
        chunk_count: int,
    ) -> bool:
        async with self._sessions() as session, session.begin():
            entity = await session.scalar(
                select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id).with_for_update()
            )
            if entity is None:
                await self._cleanup_job(session, job_id)
                return False
            await promote_vector_job(session, knowledge_base_id, job_id)
            entity.chunk_count = chunk_count
            entity.vector_status = "COMPLETED"
            entity.vector_error = None
            return True

    async def cleanup_job(self, job_id: str) -> None:
        async with self._sessions() as session, session.begin():
            await self._cleanup_job(session, job_id)

    @staticmethod
    async def _cleanup_job(session: AsyncSession, job_id: str) -> None:
        await session.execute(
            delete(VectorStore).where(
                VectorStore.metadata_json["kb_vector_job_id"].astext == job_id
            )
        )


class KnowledgeBaseVectorizationService:
    def __init__(
        self,
        repository: VectorizationRepository,
        registry_factory: Callable[[uuid.UUID], EmbeddingProviderRegistry],
        adapter: EmbeddingLlmAdapter,
        *,
        job_id_factory: Callable[[], str] | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        min_chunk_size_characters: int = MIN_CHUNK_SIZE_CHARACTERS,
        min_chunk_length_to_embed: int = MIN_CHUNK_LENGTH_TO_EMBED,
        max_num_chunks: int = MAX_NUM_CHUNKS,
    ) -> None:
        self._repository = repository
        self._registry_factory = registry_factory
        self._adapter = adapter
        self._job_id_factory = job_id_factory or (lambda: str(uuid.uuid4()))
        self._chunk_size = chunk_size
        self._min_chunk_size_characters = min_chunk_size_characters
        self._min_chunk_length_to_embed = min_chunk_length_to_embed
        self._max_num_chunks = max_num_chunks

    async def vectorize(self, knowledge_base_id: int, content: str) -> None:
        job_id = self._job_id_factory()
        try:
            chunks = split_text(
                content,
                self._chunk_size,
                self._min_chunk_size_characters,
                self._min_chunk_length_to_embed,
                self._max_num_chunks,
            )
            vectors = pending_vectors(knowledge_base_id, job_id, chunks)
            if vectors:
                context = await self._repository.provider_context(knowledge_base_id)
                if context is None:
                    return
                user_id, provider_alias = context
                provider = await self._registry_factory(user_id).get_embedding(provider_alias)
                if provider.embedding_dimensions != EMBEDDING_DIMENSIONS:
                    raise ValueError(
                        "Embedding dimension must be "
                        f"{EMBEDDING_DIMENSIONS}, got {provider.embedding_dimensions}"
                    )
                for batch in embedding_batches(vectors):
                    embeddings = await self._adapter.embed(
                        provider,
                        [vector.content for vector in batch],
                    )
                    await self._repository.store_pending_batch(
                        self._combine_embeddings(batch, embeddings)
                    )
            await self._repository.complete_job(
                knowledge_base_id,
                job_id,
                len(chunks),
            )
        except Exception as error:
            try:
                await self._repository.cleanup_job(job_id)
            except Exception:
                logger.warning(
                    "failed to clean pending vector job kbId=%s jobId=%s",
                    knowledge_base_id,
                    job_id,
                    exc_info=True,
                )
            raise BusinessException(
                ErrorCode.KNOWLEDGE_BASE_VECTORIZATION_FAILED,
                f"向量化知识库失败: {error}",
            ) from error

    @staticmethod
    def _combine_embeddings(
        vectors: Sequence[PendingVector],
        embeddings: Sequence[Sequence[float]],
    ) -> list[EmbeddedVector]:
        if len(embeddings) != len(vectors):
            raise ValueError(
                f"Embedding result count mismatch: expected {len(vectors)}, got {len(embeddings)}"
            )
        result: list[EmbeddedVector] = []
        for vector, embedding in zip(vectors, embeddings, strict=True):
            if len(embedding) != EMBEDDING_DIMENSIONS:
                raise ValueError(
                    "Embedding dimension mismatch: "
                    f"expected {EMBEDDING_DIMENSIONS}, got {len(embedding)}"
                )
            result.append(
                EmbeddedVector(
                    content=vector.content,
                    metadata=vector.metadata,
                    embedding=[float(value) for value in embedding],
                )
            )
        return result


class VectorizeStreamHandler:
    def __init__(
        self,
        repository: KnowledgeBaseVectorRepository,
        streams: RedisStreamService,
        vectorization: KnowledgeBaseVectorizationService,
    ) -> None:
        self._repository = repository
        self._streams = streams
        self._vectorization = vectorization

    async def parse(self, message: StreamMessage) -> VectorizePayload | None:
        knowledge_base_id = message.data.get(FIELD_KB_ID)
        content = message.data.get(FIELD_CONTENT)
        if knowledge_base_id is None or content is None:
            return None
        return VectorizePayload(int(knowledge_base_id), content)

    async def should_skip(self, payload: VectorizePayload) -> bool:
        return await self._repository.is_missing_or_completed(payload.knowledge_base_id)

    async def try_mark_processing(self, payload: VectorizePayload) -> bool:
        return await self._repository.update_status(
            payload.knowledge_base_id,
            "PROCESSING",
            None,
        )

    async def process(self, payload: VectorizePayload) -> None:
        if not await self._repository.exists(payload.knowledge_base_id):
            return
        await self._vectorization.vectorize(
            payload.knowledge_base_id,
            payload.content,
        )

    async def mark_completed(self, payload: VectorizePayload) -> None:
        # Promotion, chunk count, and COMPLETED must commit atomically.
        del payload

    async def retry(self, payload: VectorizePayload, retry_count: int) -> None:
        try:
            await self._streams.add(
                KB_VECTORIZE.key,
                {
                    FIELD_KB_ID: str(payload.knowledge_base_id),
                    FIELD_CONTENT: payload.content,
                    FIELD_RETRY_COUNT: str(retry_count),
                },
            )
        except Exception as error:
            await self._repository.update_status(
                payload.knowledge_base_id,
                "FAILED",
                f"重试入队失败: {error}"[:500],
            )

    async def mark_failed(self, payload: VectorizePayload, error: str) -> None:
        if error.startswith("task failed after retry "):
            error = error.replace(
                "task failed after retry ",
                "向量化 failed after retry ",
                1,
            )
        await self._repository.update_status(
            payload.knowledge_base_id,
            "FAILED",
            error,
        )
