from __future__ import annotations

import os
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlsplit

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, select

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import KnowledgeBase, VectorStore
from interview_guide.common.db.session import Database
from interview_guide.common.redis.streams import (
    KB_VECTORIZE,
    RedisStreamService,
    SequentialStreamConsumer,
)
from interview_guide.modules.knowledge_base.vectorization import (
    EMBEDDING_DIMENSIONS,
    KnowledgeBaseVectorizationService,
    KnowledgeBaseVectorRepository,
    VectorizePayload,
    VectorizeStreamHandler,
)

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
REDIS_URL = os.getenv("TEST_REDIS_URL")
TEST_FILE_HASHES = (
    "a" * 64,
    "b" * 64,
    "c" * 64,
)
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        POSTGRES_URL is None or REDIS_URL is None,
        reason="TEST_POSTGRES_URL and TEST_REDIS_URL are required",
    ),
]


def settings_from_environment() -> Settings:
    assert POSTGRES_URL is not None
    assert REDIS_URL is not None
    postgres = urlsplit(POSTGRES_URL)
    redis = urlsplit(REDIS_URL)
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="vector-worker-integration-key",
        POSTGRES_HOST=postgres.hostname or "127.0.0.1",
        POSTGRES_PORT=postgres.port or 5432,
        POSTGRES_DB=postgres.path.removeprefix("/"),
        POSTGRES_USER=postgres.username or "postgres",
        POSTGRES_PASSWORD=postgres.password or "",
        REDIS_HOST=redis.hostname or "127.0.0.1",
        REDIS_PORT=redis.port or 6379,
        REDIS_DB=int(redis.path.removeprefix("/") or "0"),
    )


@pytest.fixture
async def vector_resources() -> AsyncIterator[tuple[Database, Redis]]:
    assert REDIS_URL is not None
    database = Database(settings_from_environment())
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await redis.flushdb()
    await cleanup_test_records(database)
    try:
        yield database, redis
    finally:
        await cleanup_test_records(database)
        await redis.flushdb()
        await redis.aclose()
        await database.close()


async def cleanup_test_records(database: Database) -> None:
    async with database.sessions() as session, session.begin():
        knowledge_base_ids = list(
            await session.scalars(
                select(KnowledgeBase.id).where(KnowledgeBase.file_hash.in_(TEST_FILE_HASHES))
            )
        )
        for knowledge_base_id in knowledge_base_ids:
            target = str(knowledge_base_id)
            await session.execute(
                delete(VectorStore).where(
                    (VectorStore.metadata_json["kb_id"].astext == target)
                    | (VectorStore.metadata_json["kb_target_id"].astext == target)
                )
            )
        await session.execute(
            delete(KnowledgeBase).where(KnowledgeBase.file_hash.in_(TEST_FILE_HASHES))
        )


async def create_knowledge_base(
    database: Database,
    *,
    file_hash: str,
    vector_status: str,
) -> int:
    async with database.sessions() as session, session.begin():
        entity = KnowledgeBase(
            access_count=0,
            category="integration",
            chunk_count=99,
            content_type="text/plain",
            file_hash=file_hash,
            file_size=11,
            name="vector worker integration",
            original_filename="vector-worker.txt",
            question_count=0,
            uploaded_at=datetime(2026, 8, 16, 8, 0),
            vector_error="old error",
            vector_status=vector_status,
        )
        session.add(entity)
        await session.flush()
        return entity.id


async def add_old_vector(database: Database, knowledge_base_id: int) -> None:
    async with database.sessions() as session, session.begin():
        session.add(
            VectorStore(
                content="old formal vector",
                metadata_json={"kb_id": str(knowledge_base_id)},
                embedding=[0.0] * EMBEDDING_DIMENSIONS,
            )
        )


@dataclass
class FakeEmbeddingProviderRegistry:
    calls: int = 0

    async def get_embedding(
        self,
        provider_id: str | None = None,
    ) -> ProviderConfig:
        assert provider_id is None
        self.calls += 1
        return ProviderConfig(
            provider_id="fake-integration-embedding",
            base_url="http://fake.invalid/v1",
            api_key="fake-key",
            model="fake-chat",
            embedding_model="fake-embedding",
            embedding_dimensions=EMBEDDING_DIMENSIONS,
            supports_embedding=True,
        )


@dataclass
class FakeEmbeddingLlmAdapter:
    fail_last_batch: bool = False
    batch_sizes: list[int] = field(default_factory=list)

    async def embed(
        self,
        provider: ProviderConfig,
        inputs: Sequence[str],
    ) -> list[list[float]]:
        assert provider.provider_id == "fake-integration-embedding"
        self.batch_sizes.append(len(inputs))
        if self.fail_last_batch and len(inputs) < 10:
            raise RuntimeError("fake integration embedding failure")
        return [[float(index + 1)] * EMBEDDING_DIMENSIONS for index, _ in enumerate(inputs)]


def build_consumer(
    database: Database,
    streams: RedisStreamService,
    registry: FakeEmbeddingProviderRegistry,
    adapter: FakeEmbeddingLlmAdapter,
) -> SequentialStreamConsumer[VectorizePayload]:
    repository = KnowledgeBaseVectorRepository(database.sessions)
    vectorization = KnowledgeBaseVectorizationService(
        repository,
        registry,
        adapter,
        job_id_factory=lambda: "integration-job-success",
        chunk_size=1,
        min_chunk_size_characters=0,
        min_chunk_length_to_embed=0,
    )
    return SequentialStreamConsumer(
        streams,
        KB_VECTORIZE,
        "vectorize-consumer-integration",
        VectorizeStreamHandler(repository, streams, vectorization),
    )


@pytest.mark.asyncio
async def test_fake_embedding_vector_worker_promotes_and_completes_atomically(
    vector_resources: tuple[Database, Redis],
) -> None:
    database, redis = vector_resources
    knowledge_base_id = await create_knowledge_base(
        database,
        file_hash=TEST_FILE_HASHES[0],
        vector_status="PENDING",
    )
    await add_old_vector(database, knowledge_base_id)
    streams = RedisStreamService(redis)
    registry = FakeEmbeddingProviderRegistry()
    adapter = FakeEmbeddingLlmAdapter()
    consumer = build_consumer(database, streams, registry, adapter)
    await streams.ensure_group(KB_VECTORIZE)
    await streams.add(
        KB_VECTORIZE.key,
        {
            "kbId": str(knowledge_base_id),
            "content": "one two three four five six seven eight nine ten eleven",
            "retryCount": "0",
        },
        message_id="1-0",
    )

    messages = await streams.read_batch(
        KB_VECTORIZE,
        "vectorize-consumer-integration",
        block_ms=10,
        pending_idle_ms=60_000,
    )
    await consumer.process_message(messages[0])

    async with database.sessions() as session:
        entity = await session.get(KnowledgeBase, knowledge_base_id)
        vectors = list(
            await session.scalars(
                select(VectorStore)
                .where(VectorStore.metadata_json["kb_id"].astext == str(knowledge_base_id))
                .order_by(VectorStore.content)
            )
        )
    assert entity is not None
    assert entity.vector_status == "COMPLETED"
    assert entity.vector_error is None
    assert entity.chunk_count == 11
    assert [vector.content for vector in vectors] == [
        "eight",
        "eleven",
        "five",
        "four",
        "nine",
        "one",
        "seven",
        "six",
        "ten",
        "three",
        "two",
    ]
    assert all(vector.metadata_json == {"kb_id": str(knowledge_base_id)} for vector in vectors)
    assert all(
        vector.embedding is not None and len(vector.embedding) == EMBEDDING_DIMENSIONS
        for vector in vectors
    )
    assert registry.calls == 1
    assert adapter.batch_sizes == [10, 1]
    pending = await redis.xpending(KB_VECTORIZE.key, KB_VECTORIZE.group)
    assert pending["pending"] == 0


@pytest.mark.asyncio
async def test_fake_embedding_vector_worker_retries_cleans_and_finally_fails(
    vector_resources: tuple[Database, Redis],
) -> None:
    database, redis = vector_resources
    knowledge_base_id = await create_knowledge_base(
        database,
        file_hash=TEST_FILE_HASHES[1],
        vector_status="PENDING",
    )
    await add_old_vector(database, knowledge_base_id)
    streams = RedisStreamService(redis)
    registry = FakeEmbeddingProviderRegistry()
    adapter = FakeEmbeddingLlmAdapter(fail_last_batch=True)
    repository = KnowledgeBaseVectorRepository(database.sessions)
    job_ids = iter(
        [
            "integration-job-retry-0",
            "integration-job-retry-1",
            "integration-job-retry-2",
            "integration-job-retry-3",
        ]
    )
    vectorization = KnowledgeBaseVectorizationService(
        repository,
        registry,
        adapter,
        job_id_factory=lambda: next(job_ids),
        chunk_size=1,
        min_chunk_size_characters=0,
        min_chunk_length_to_embed=0,
    )
    consumer = SequentialStreamConsumer(
        streams,
        KB_VECTORIZE,
        "vectorize-consumer-integration",
        VectorizeStreamHandler(repository, streams, vectorization),
    )
    await streams.ensure_group(KB_VECTORIZE)
    await streams.add(
        KB_VECTORIZE.key,
        {
            "kbId": str(knowledge_base_id),
            "content": "one two three four five six seven eight nine ten eleven",
            "retryCount": "0",
        },
        message_id="1-0",
    )

    for retry_count in range(4):
        messages = await streams.read_batch(
            KB_VECTORIZE,
            "vectorize-consumer-integration",
            block_ms=10,
            pending_idle_ms=60_000,
        )
        assert len(messages) == 1
        assert messages[0].retry_count == retry_count
        await consumer.process_message(messages[0])
        if retry_count < 3:
            async with database.sessions() as session:
                processing = await session.get(KnowledgeBase, knowledge_base_id)
            assert processing is not None
            assert processing.vector_status == "PROCESSING"
            assert processing.vector_error is None

    async with database.sessions() as session:
        entity = await session.get(KnowledgeBase, knowledge_base_id)
        formal_vectors = list(
            await session.scalars(
                select(VectorStore).where(
                    VectorStore.metadata_json["kb_id"].astext == str(knowledge_base_id)
                )
            )
        )
        pending_count = len(
            list(
                await session.scalars(
                    select(VectorStore.id).where(
                        VectorStore.metadata_json["kb_target_id"].astext == str(knowledge_base_id)
                    )
                )
            )
        )
    assert entity is not None
    assert entity.vector_status == "FAILED"
    assert entity.vector_error is not None
    assert entity.vector_error.startswith("向量化 failed after retry 3:")
    assert [vector.content for vector in formal_vectors] == ["old formal vector"]
    assert pending_count == 0
    assert registry.calls == 4
    assert adapter.batch_sizes == [10, 1] * 4
    pending = await redis.xpending(KB_VECTORIZE.key, KB_VECTORIZE.group)
    assert pending["pending"] == 0
    assert await redis.xlen(KB_VECTORIZE.key) == 4


@pytest.mark.asyncio
async def test_vector_worker_acks_missing_and_completed_entities_without_embedding(
    vector_resources: tuple[Database, Redis],
) -> None:
    database, redis = vector_resources
    completed_id = await create_knowledge_base(
        database,
        file_hash=TEST_FILE_HASHES[2],
        vector_status="COMPLETED",
    )
    streams = RedisStreamService(redis)
    registry = FakeEmbeddingProviderRegistry()
    adapter = FakeEmbeddingLlmAdapter()
    consumer = build_consumer(database, streams, registry, adapter)
    await streams.ensure_group(KB_VECTORIZE)
    await streams.add(
        KB_VECTORIZE.key,
        {"kbId": str(completed_id), "content": "completed"},
        message_id="1-0",
    )
    await streams.add(
        KB_VECTORIZE.key,
        {"kbId": "9223372036854775807", "content": "missing"},
        message_id="2-0",
    )
    await streams.add(
        KB_VECTORIZE.key,
        {"kbId": "invalid", "content": "malformed"},
        message_id="3-0",
    )
    await streams.add(
        KB_VECTORIZE.key,
        {"kbId": str(completed_id)},
        message_id="4-0",
    )

    messages = await streams.read_batch(
        KB_VECTORIZE,
        "vectorize-consumer-integration",
        block_ms=10,
        pending_idle_ms=60_000,
    )
    for message in messages:
        await consumer.process_message(message)

    assert registry.calls == 0
    assert adapter.batch_sizes == []
    pending = await redis.xpending(KB_VECTORIZE.key, KB_VECTORIZE.group)
    assert pending["pending"] == 0
