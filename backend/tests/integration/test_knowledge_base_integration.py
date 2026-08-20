from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, func, select

from interview_guide.common.ai.adapter import ChatResult, ProviderConfig
from interview_guide.common.ai.prompts import PromptRepository
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import (
    KnowledgeBase,
    RagChatMessage,
    RagChatSession,
    RagSessionKnowledgeBase,
    VectorStore,
)
from interview_guide.common.db.session import Database
from interview_guide.common.errors import BusinessException
from interview_guide.common.redis.streams import KB_VECTORIZE, RedisStreamService
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.infrastructure.file.document import create_document_parser
from interview_guide.infrastructure.file.hash import sha256_bytes
from interview_guide.infrastructure.storage.keys import FileKeyGenerator
from interview_guide.infrastructure.storage.s3 import S3Storage
from interview_guide.modules.knowledge_base.models import QueryRequest
from interview_guide.modules.knowledge_base.query_service import (
    KnowledgeBaseQueryService,
    QueryConfiguration,
)
from interview_guide.modules.knowledge_base.repository import (
    KnowledgeBaseQueryRepository,
)
from interview_guide.modules.knowledge_base.service import KnowledgeBaseService
from interview_guide.modules.knowledge_base.vectorization import EMBEDDING_DIMENSIONS

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
REDIS_URL = os.getenv("TEST_REDIS_URL")
S3_ENDPOINT = os.getenv("TEST_S3_ENDPOINT")
S3_ACCESS_KEY = os.getenv("TEST_S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("TEST_S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("TEST_S3_BUCKET", "interview-guide-integration")
FIXED_NOW = datetime(2026, 8, 16, 8, 0)
SAMPLES = Path(__file__).resolve().parents[1] / "fixtures" / "knowledge-base"
RESOURCES = Path(__file__).resolve().parents[2] / "resources"
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        POSTGRES_URL is None or REDIS_URL is None or S3_ENDPOINT is None,
        reason="TEST_POSTGRES_URL, TEST_REDIS_URL, and TEST_S3_ENDPOINT are required",
    ),
]


def settings_from_environment() -> Settings:
    assert POSTGRES_URL is not None
    assert REDIS_URL is not None
    assert S3_ENDPOINT is not None
    postgres = urlsplit(POSTGRES_URL)
    redis = urlsplit(REDIS_URL)
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="knowledge-base-integration-key",
        APP_STORAGE_ENDPOINT=S3_ENDPOINT,
        APP_STORAGE_ACCESS_KEY=S3_ACCESS_KEY,
        APP_STORAGE_SECRET_KEY=S3_SECRET_KEY,
        APP_STORAGE_BUCKET=S3_BUCKET,
        APP_STORAGE_AUTO_CREATE_BUCKET=True,
        POSTGRES_HOST=postgres.hostname or "127.0.0.1",
        POSTGRES_PORT=postgres.port or 5432,
        POSTGRES_DB=postgres.path.removeprefix("/"),
        POSTGRES_USER=postgres.username or "postgres",
        POSTGRES_PASSWORD=postgres.password or "",
        REDIS_HOST=redis.hostname or "127.0.0.1",
        REDIS_PORT=redis.port or 6379,
        REDIS_DB=int(redis.path.removeprefix("/") or "0"),
    )


@dataclass
class KnowledgeBaseResources:
    database: Database
    redis: Redis
    streams: RedisStreamService
    storage: S3Storage
    parser: object
    executor: BlockingExecutor
    object_keys: list[str] = field(default_factory=list)


@pytest.fixture
async def knowledge_base_resources() -> AsyncIterator[KnowledgeBaseResources]:
    assert REDIS_URL is not None
    settings = settings_from_environment()
    database = Database(settings)
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    executor = BlockingExecutor(max_workers=2)
    storage = S3Storage(
        settings,
        executor,
        key_generator=FileKeyGenerator(
            now=lambda: FIXED_NOW,
            uuid_factory=lambda: uuid.UUID("87654321-0000-0000-0000-000000000000"),
        ),
    )
    await storage.start()
    resources = KnowledgeBaseResources(
        database=database,
        redis=redis,
        streams=RedisStreamService(redis),
        storage=storage,
        parser=create_document_parser(settings, executor),
        executor=executor,
    )
    await redis.delete(KB_VECTORIZE.key)
    await cleanup_database(database)
    try:
        yield resources
    finally:
        await cleanup_database(database)
        for key in resources.object_keys:
            await storage.delete(key)
        await redis.delete(KB_VECTORIZE.key)
        await redis.aclose()
        await database.close()
        await executor.shutdown()


async def cleanup_database(database: Database) -> None:
    hashes = [
        sha256_bytes((SAMPLES / "fixed-knowledge-base.txt").read_bytes()),
        sha256_bytes((SAMPLES / "fixed-knowledge-base.md").read_bytes()),
        sha256_bytes(b"fixed queue failure content"),
    ]
    async with database.sessions() as session, session.begin():
        knowledge_base_ids = list(
            await session.scalars(
                select(KnowledgeBase.id).where(KnowledgeBase.file_hash.in_(hashes))
            )
        )
        if knowledge_base_ids:
            await session.execute(
                delete(RagSessionKnowledgeBase).where(
                    RagSessionKnowledgeBase.knowledge_base_id.in_(knowledge_base_ids)
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
                delete(KnowledgeBase).where(KnowledgeBase.id.in_(knowledge_base_ids))
            )
        await session.execute(
            delete(RagChatSession).where(RagChatSession.title.like("knowledge-base-integration-%"))
        )


def service(
    resources: KnowledgeBaseResources,
    session: object,
    streams: object | None = None,
) -> KnowledgeBaseService:
    return KnowledgeBaseService(
        session,  # type: ignore[arg-type]
        resources.database.sessions,
        resources.storage,
        streams or resources.streams,  # type: ignore[arg-type]
        resources.parser,  # type: ignore[arg-type]
        now=lambda: FIXED_NOW,
    )


@pytest.mark.asyncio
async def test_real_infrastructure_knowledge_base_business_flow_with_no_embedding(
    knowledge_base_resources: KnowledgeBaseResources,
) -> None:
    resources = knowledge_base_resources
    text = (SAMPLES / "fixed-knowledge-base.txt").read_bytes()
    markdown = (SAMPLES / "fixed-knowledge-base.md").read_bytes()
    async with resources.database.sessions() as session:
        knowledge_bases = service(resources, session)
        first = await knowledge_bases.upload(
            text,
            "fixed-knowledge-base.txt",
            "text/plain",
            "  固定名称  ",
            "  基础  ",
        )
        first_data = first["knowledgeBase"]
        assert isinstance(first_data, dict)
        first_id = int(first_data["id"])
        first_storage = first["storage"]
        assert isinstance(first_storage, dict)
        resources.object_keys.append(str(first_storage["fileKey"]))
        assert first_data["name"] == "  固定名称  "
        assert first_data["category"] == "基础"
        assert first_data["vectorStatus"] == "PENDING"

        duplicate = await knowledge_bases.upload(
            text,
            "duplicate-name.txt",
            "text/plain",
            None,
            None,
        )
        assert duplicate["duplicate"] is True
        detail = await knowledge_bases.detail(first_id)
        assert detail is not None
        assert detail["accessCount"] == 2
        assert detail["lastAccessedAt"] == FIXED_NOW
        assert detail["chunkCount"] == 0

        second = await knowledge_bases.upload(
            markdown,
            "fixed-knowledge-base.md",
            "text/markdown",
            "Markdown 样本",
            None,
        )
        second_data = second["knowledgeBase"]
        assert isinstance(second_data, dict)
        second_id = int(second_data["id"])
        second_storage = second["storage"]
        assert isinstance(second_storage, dict)
        second_key = str(second_storage["fileKey"])
        resources.object_keys.append(second_key)

        await knowledge_bases.update_category(second_id, "文档")
        assert await knowledge_bases.categories() == ["基础", "文档"]
        assert [row["id"] for row in await knowledge_bases.list_by_category("文档")] == [second_id]
        assert await knowledge_bases.search("文档") == []
        assert [row["id"] for row in await knowledge_bases.search("Markdown")] == [second_id]
        assert await knowledge_bases.statistics() == {
            "totalCount": 2,
            "totalQuestionCount": 0,
            "totalAccessCount": 3,
            "completedCount": 0,
            "processingCount": 0,
        }

        downloaded, headers = await knowledge_bases.download(first_id)
        assert downloaded == text
        assert headers == {
            "Content-Disposition": (
                'attachment; filename="fixed-knowledge-base.txt"; '
                "filename*=UTF-8''fixed-knowledge-base.txt"
            ),
            "Content-Type": "text/plain",
        }

        await resources.redis.delete(KB_VECTORIZE.key)
        await knowledge_bases.revectorize(first_id)
        messages = await resources.redis.xrange(KB_VECTORIZE.key)
        assert len(messages) == 1
        assert messages[0][1] == {
            "kbId": str(first_id),
            "content": text.decode().strip(),
            "retryCount": "0",
        }
        revectorized = await knowledge_bases.detail(first_id)
        assert revectorized is not None
        assert revectorized["vectorStatus"] == "PENDING"
        assert revectorized["vectorError"] is None

        await knowledge_bases.update_question_counts([first_id, second_id, first_id])
        first_after_count = await knowledge_bases.detail(first_id)
        second_after_count = await knowledge_bases.detail(second_id)
        assert first_after_count is not None
        assert second_after_count is not None
        assert first_after_count["questionCount"] == 1
        assert second_after_count["questionCount"] == 1
        assert (await knowledge_bases.statistics())["totalQuestionCount"] == 0

        async with resources.database.sessions() as seed_session, seed_session.begin():
            rag_session = RagChatSession(
                created_at=FIXED_NOW,
                is_pinned=False,
                message_count=0,
                status="ACTIVE",
                title="knowledge-base-integration-delete",
                updated_at=FIXED_NOW,
            )
            seed_session.add(rag_session)
            await seed_session.flush()
            seed_session.add(
                RagSessionKnowledgeBase(
                    session_id=rag_session.id,
                    knowledge_base_id=second_id,
                )
            )
            seed_session.add(
                VectorStore(
                    content="formal vector",
                    metadata_json={"kb_id": str(second_id)},
                    embedding=[0.0] * EMBEDDING_DIMENSIONS,
                )
            )
        assert await resources.storage.exists(second_key)

        await knowledge_bases.delete(second_id)

    async with resources.database.sessions() as verification:
        assert await verification.get(KnowledgeBase, second_id) is None
        assert (
            await verification.scalar(
                select(RagSessionKnowledgeBase).where(
                    RagSessionKnowledgeBase.knowledge_base_id == second_id
                )
            )
            is None
        )
        vector_count = await verification.scalar(
            select(VectorStore.id).where(
                VectorStore.metadata_json["kb_id"].astext == str(second_id)
            )
        )
        assert vector_count is None
    assert not await resources.storage.exists(second_key)


class FailingStreams:
    async def add(
        self,
        stream_key: str,
        fields: dict[str, str],
        *,
        max_len: int = 1000,
        message_id: str = "*",
    ) -> str:
        del stream_key, fields, max_len, message_id
        raise RuntimeError("fixed enqueue failure")


@pytest.mark.asyncio
async def test_real_database_marks_failed_when_upload_and_revectorize_enqueue_fail(
    knowledge_base_resources: KnowledgeBaseResources,
) -> None:
    resources = knowledge_base_resources
    data = b"fixed queue failure content"
    async with resources.database.sessions() as session:
        knowledge_bases = service(resources, session, FailingStreams())
        result = await knowledge_bases.upload(
            data,
            "enqueue-failure.txt",
            "text/plain",
            None,
            None,
        )
        response = result["knowledgeBase"]
        storage = result["storage"]
        assert isinstance(response, dict)
        assert isinstance(storage, dict)
        resources.object_keys.append(str(storage["fileKey"]))
        assert response["vectorStatus"] == "PENDING"
        knowledge_base_id = int(response["id"])
        await knowledge_bases.revectorize(knowledge_base_id)

    async with resources.database.sessions() as verification:
        entity = await verification.get(KnowledgeBase, knowledge_base_id)
        assert entity is not None
        assert entity.vector_status == "FAILED"
        assert entity.vector_error == "任务入队失败: fixed enqueue failure"


@pytest.mark.asyncio
async def test_batch_question_count_rolls_back_for_missing_id(
    knowledge_base_resources: KnowledgeBaseResources,
) -> None:
    resources = knowledge_base_resources
    text = (SAMPLES / "fixed-knowledge-base.txt").read_bytes()
    async with resources.database.sessions() as session:
        knowledge_bases = service(resources, session)
        result = await knowledge_bases.upload(
            text,
            "fixed-knowledge-base.txt",
            "text/plain",
            "",
            "",
        )
        response = result["knowledgeBase"]
        storage = result["storage"]
        assert isinstance(response, dict)
        assert isinstance(storage, dict)
        resources.object_keys.append(str(storage["fileKey"]))
        knowledge_base_id = int(response["id"])
        assert response["name"] == "fixed-knowledge-base"
        detail = await knowledge_bases.detail(knowledge_base_id)
        assert detail is not None
        assert detail["category"] is None

        with pytest.raises(BusinessException, match="知识库不存在: 9223372036854775807"):
            await knowledge_bases.update_question_counts([knowledge_base_id, 9223372036854775807])

    async with resources.database.sessions() as verification:
        entity = await verification.get(KnowledgeBase, knowledge_base_id)
        assert entity is not None
        assert entity.question_count == 0


def fixed_query_vector(x: float, y: float) -> list[float]:
    return [x, y] + [0.0] * (EMBEDDING_DIMENSIONS - 2)


class FixedFakeQueryRegistry:
    def __init__(self) -> None:
        self.chat_provider = ProviderConfig(
            provider_id="fixed-fake-chat",
            base_url="https://fake.invalid",
            api_key="fixed-fake-key",
            model="fixed-fake-chat",
        )
        self.embedding_provider = ProviderConfig(
            provider_id="fixed-fake-embedding",
            base_url="https://fake.invalid",
            api_key="fixed-fake-key",
            model="fixed-fake-chat",
            embedding_model="fixed-fake-embedding",
            embedding_dimensions=EMBEDDING_DIMENSIONS,
            supports_embedding=True,
        )

    async def get_chat(self, provider_id: str | None = None) -> ProviderConfig:
        del provider_id
        return self.chat_provider

    async def get_embedding(
        self,
        provider_id: str | None = None,
    ) -> ProviderConfig:
        del provider_id
        return self.embedding_provider


class FixedFakeQueryAdapter:
    def __init__(self) -> None:
        self.messages: list[list[dict[str, Any]]] = []
        self.stream_sequences = [
            ["固定", "流式回答"],
            ["取" * 120, "取消后不应读取"],
        ]
        self.stream_close_count = 0

    async def chat(
        self,
        provider: ProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        del provider, tools, tool_choice, temperature
        self.messages.append(list(messages))
        return ChatResult(
            content="固定同步回答",
            message={"role": "assistant", "content": "固定同步回答"},
            usage=None,
            raw={},
        )

    async def stream_chat(
        self,
        provider: ProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        del provider, tools, tool_choice, temperature
        self.messages.append(list(messages))
        chunks = self.stream_sequences.pop(0)
        try:
            for chunk in chunks:
                yield {"choices": [{"delta": {"content": chunk}}]}
        finally:
            self.stream_close_count += 1

    async def embed(
        self,
        provider: ProviderConfig,
        inputs: Sequence[str],
    ) -> list[list[float]]:
        del provider
        assert inputs
        return [fixed_query_vector(1.0, 0.0) for _ in inputs]


@pytest.mark.asyncio
async def test_fixed_fake_query_uses_real_postgres_pgvector_and_leaves_redis_clean(
    knowledge_base_resources: KnowledgeBaseResources,
) -> None:
    resources = knowledge_base_resources
    text = (SAMPLES / "fixed-knowledge-base.txt").read_bytes()
    markdown = (SAMPLES / "fixed-knowledge-base.md").read_bytes()
    async with resources.database.sessions() as session:
        knowledge_bases = service(resources, session)
        first = await knowledge_bases.upload(
            text,
            "fixed-knowledge-base.txt",
            "text/plain",
            "固定查询库一",
            None,
        )
        second = await knowledge_bases.upload(
            markdown,
            "fixed-knowledge-base.md",
            "text/markdown",
            "固定查询库二",
            None,
        )
        first_data = first["knowledgeBase"]
        second_data = second["knowledgeBase"]
        first_storage = first["storage"]
        second_storage = second["storage"]
        assert isinstance(first_data, dict)
        assert isinstance(second_data, dict)
        assert isinstance(first_storage, dict)
        assert isinstance(second_storage, dict)
        first_id = int(first_data["id"])
        second_id = int(second_data["id"])
        resources.object_keys.extend(
            [
                str(first_storage["fileKey"]),
                str(second_storage["fileKey"]),
            ]
        )

    async with resources.database.sessions() as seed_session, seed_session.begin():
        seed_session.add_all(
            [
                VectorStore(
                    content="第一相关片段",
                    metadata_json={"kb_id": str(first_id)},
                    embedding=fixed_query_vector(1.0, 0.0),
                ),
                VectorStore(
                    content="第二相关片段",
                    metadata_json={"kb_id": str(first_id)},
                    embedding=fixed_query_vector(0.8, 0.6),
                ),
                VectorStore(
                    content="低分片段",
                    metadata_json={"kb_id": str(first_id)},
                    embedding=fixed_query_vector(0.0, 1.0),
                ),
                VectorStore(
                    content="另一个知识库片段",
                    metadata_json={"kb_id": str(second_id)},
                    embedding=fixed_query_vector(0.6, 0.8),
                ),
            ]
        )

    query_repository = KnowledgeBaseQueryRepository(resources.database.sessions)
    hits = await query_repository.similarity_search(
        [first_id],
        fixed_query_vector(1.0, 0.0),
        10,
        0.5,
    )
    assert [hit.content for hit in hits] == ["第一相关片段", "第二相关片段"]
    assert [hit.score for hit in hits] == pytest.approx([1.0, 0.8])

    await resources.redis.delete(KB_VECTORIZE.key)
    adapter = FixedFakeQueryAdapter()
    query_service = KnowledgeBaseQueryService(
        query_repository,
        FixedFakeQueryRegistry(),
        adapter,
        PromptRepository(RESOURCES),
        QueryConfiguration(rewrite_enabled=False),
    )
    response = await query_service.query(
        QueryRequest(
            knowledgeBaseIds=[first_id, second_id, first_id],
            question="固定问题",
        )
    )
    assert response.answer == "固定同步回答"
    assert response.knowledge_base_id == first_id
    assert response.knowledge_base_name == "固定查询库一、固定查询库二、固定查询库一"

    stream = await query_service.answer_question_stream([first_id], "固定问题")
    assert [chunk async for chunk in stream] == ["固定流式回答"]

    cancelled_stream = await query_service.answer_question_stream(
        [first_id],
        "固定问题",
    )
    assert await anext(cancelled_stream) == "取" * 120
    await cancelled_stream.aclose()
    assert adapter.stream_close_count == 2

    assert await resources.redis.xrange(KB_VECTORIZE.key) == []
    async with resources.database.sessions() as verification:
        first_entity = await verification.get(KnowledgeBase, first_id)
        second_entity = await verification.get(KnowledgeBase, second_id)
        assert first_entity is not None
        assert second_entity is not None
        assert first_entity.question_count == 3
        assert second_entity.question_count == 1
        message_count = await verification.scalar(select(func.count()).select_from(RagChatMessage))
        assert message_count == 0
        vector_count = await verification.scalar(
            select(func.count())
            .select_from(VectorStore)
            .where(VectorStore.metadata_json["kb_id"].astext.in_([str(first_id), str(second_id)]))
        )
        assert vector_count == 4
