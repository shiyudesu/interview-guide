from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, select

from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import (
    KnowledgeBase,
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
from interview_guide.modules.knowledge_base.service import KnowledgeBaseService
from interview_guide.modules.knowledge_base.vectorization import EMBEDDING_DIMENSIONS

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
REDIS_URL = os.getenv("TEST_REDIS_URL")
S3_ENDPOINT = os.getenv("TEST_S3_ENDPOINT")
FIXED_NOW = datetime(2026, 8, 16, 8, 0)
SAMPLES = Path(__file__).resolve().parents[3] / "migration" / "samples" / "knowledge-base"
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
        APP_STORAGE_ACCESS_KEY="comparison-access",
        APP_STORAGE_SECRET_KEY="comparison-secret",
        APP_STORAGE_BUCKET="interview-guide-python",
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
                        | (VectorStore.metadata_json["kb_id_long"].astext == target)
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
            seed_session.add_all(
                [
                    VectorStore(
                        content="formal vector",
                        metadata_json={"kb_id": str(second_id)},
                        embedding=[0.0] * EMBEDDING_DIMENSIONS,
                    ),
                    VectorStore(
                        content="legacy vector",
                        metadata_json={"kb_id_long": str(second_id)},
                        embedding=[0.0] * EMBEDDING_DIMENSIONS,
                    ),
                ]
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
                (VectorStore.metadata_json["kb_id"].astext == str(second_id))
                | (VectorStore.metadata_json["kb_id_long"].astext == str(second_id))
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
