from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

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
DEFAULT_MAX_CHUNK_CHARACTERS = 2400


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


def split_text(
    content: str,
    max_characters: int = DEFAULT_MAX_CHUNK_CHARACTERS,
) -> list[str]:
    if max_characters < 1:
        raise ValueError("max_characters must be at least 1")
    paragraphs = [value.strip() for value in content.split("\n\n") if value.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_characters:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(paragraph) > max_characters:
            chunks.append(paragraph[:max_characters])
            paragraph = paragraph[max_characters:]
        current = paragraph
    if current:
        chunks.append(current)
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
               OR (
                    metadata->>'kb_id_long' IS NOT NULL
                    AND (metadata->>'kb_id_long')::bigint = :knowledge_base_id
               )
            """
        ),
        {
            "target": str(knowledge_base_id),
            "knowledge_base_id": knowledge_base_id,
        },
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
              AND metadata->>'kb_id' = :pending
            """
        ),
        {
            "target": str(knowledge_base_id),
            "job_id": job_id,
            "pending": f"pending:{knowledge_base_id}:{job_id}",
        },
    )


class KnowledgeBaseVectorRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def is_missing_or_completed(self, knowledge_base_id: int) -> bool:
        async with self._sessions() as session:
            entity = await session.get(KnowledgeBase, knowledge_base_id)
            return entity is None or entity.vector_status == "COMPLETED"

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
        registry: EmbeddingProviderRegistry,
        adapter: EmbeddingLlmAdapter,
        *,
        job_id_factory: Callable[[], str] | None = None,
        max_chunk_characters: int = DEFAULT_MAX_CHUNK_CHARACTERS,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._adapter = adapter
        self._job_id_factory = job_id_factory or (lambda: str(uuid.uuid4()))
        self._max_chunk_characters = max_chunk_characters

    async def vectorize(self, knowledge_base_id: int, content: str) -> None:
        job_id = self._job_id_factory()
        try:
            chunks = split_text(content, self._max_chunk_characters)
            vectors = pending_vectors(knowledge_base_id, job_id, chunks)
            if vectors:
                provider = await self._registry.get_embedding()
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
        await self._repository.update_status(
            payload.knowledge_base_id,
            "FAILED",
            error,
        )
