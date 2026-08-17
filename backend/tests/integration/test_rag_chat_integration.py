from __future__ import annotations

import os
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlsplit

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, event, func, select

from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import (
    KnowledgeBase,
    RagChatMessage,
    RagChatSession,
    RagSessionKnowledgeBase,
)
from interview_guide.common.db.session import Database
from interview_guide.common.errors import BusinessException
from interview_guide.common.redis.streams import KB_VECTORIZE
from interview_guide.modules.knowledge_base.query_service import STREAM_ERROR_RESPONSE
from interview_guide.modules.knowledge_base.rag_chat_api import rag_chat_sse_stream
from interview_guide.modules.knowledge_base.rag_chat_models import CreateSessionRequest
from interview_guide.modules.knowledge_base.rag_chat_repository import RagChatRepository
from interview_guide.modules.knowledge_base.rag_chat_service import RagChatService

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
REDIS_URL = os.getenv("TEST_REDIS_URL")
FIXED_NOW = datetime(2026, 8, 16, 8, 0)
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        POSTGRES_URL is None or REDIS_URL is None,
        reason="TEST_POSTGRES_URL and TEST_REDIS_URL are required",
    ),
]


def integration_settings() -> Settings:
    assert POSTGRES_URL is not None
    assert REDIS_URL is not None
    postgres = urlsplit(POSTGRES_URL)
    redis = urlsplit(REDIS_URL)
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="rag-chat-integration-key",
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
class ExplicitFakeRagQueryService:
    streams: list[list[str]]
    calls: list[tuple[list[int | None], str | None, list[dict[str, str]]]] = field(
        default_factory=list
    )
    closed: int = 0

    async def answer_question_stream(
        self,
        knowledge_base_ids: Sequence[int | None] | None,
        question: str | None,
        history: Sequence[dict[str, str]] | None = None,
    ) -> AsyncIterator[str]:
        self.calls.append(
            (
                list(knowledge_base_ids or ()),
                question,
                list(history or ()),
            )
        )
        chunks = self.streams.pop(0)

        async def iterate() -> AsyncIterator[str]:
            try:
                for chunk in chunks:
                    yield chunk
            finally:
                self.closed += 1

        return iterate()


async def cleanup(database: Database) -> None:
    async with database.sessions() as session, session.begin():
        session_ids = list(
            await session.scalars(
                select(RagChatSession.id).where(RagChatSession.title.like("rag-chat-integration-%"))
            )
        )
        if session_ids:
            await session.execute(
                delete(RagSessionKnowledgeBase).where(
                    RagSessionKnowledgeBase.session_id.in_(session_ids)
                )
            )
            await session.execute(
                delete(RagChatMessage).where(RagChatMessage.session_id.in_(session_ids))
            )
            await session.execute(delete(RagChatSession).where(RagChatSession.id.in_(session_ids)))
        await session.execute(
            delete(KnowledgeBase).where(KnowledgeBase.file_hash.like("rag-chat-integration-%"))
        )


async def seed_knowledge_bases(database: Database) -> tuple[int, int]:
    async with database.sessions() as session, session.begin():
        entities = [
            KnowledgeBase(
                access_count=1,
                chunk_count=1,
                content_type="text/plain",
                file_hash="rag-chat-integration-one",
                file_size=10,
                name="rag-chat-integration-知识库一",
                original_filename="one.txt",
                question_count=0,
                question_gen_status="NONE",
                uploaded_at=FIXED_NOW,
                last_accessed_at=FIXED_NOW,
                vector_status="COMPLETED",
            ),
            KnowledgeBase(
                access_count=1,
                chunk_count=2,
                content_type="text/markdown",
                file_hash="rag-chat-integration-two",
                file_size=20,
                name="rag-chat-integration-知识库二",
                original_filename="two.md",
                question_count=0,
                question_gen_status="NONE",
                uploaded_at=FIXED_NOW,
                last_accessed_at=FIXED_NOW,
                vector_status="COMPLETED",
            ),
        ]
        session.add_all(entities)
        await session.flush()
        return entities[0].id, entities[1].id


@pytest.mark.asyncio
async def test_real_postgres_rag_chat_crud_stream_error_and_cancel_leave_redis_clean() -> None:
    assert REDIS_URL is not None
    database = Database(integration_settings())
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await cleanup(database)
    await redis.delete(KB_VECTORIZE.key)
    first_id, second_id = await seed_knowledge_bases(database)
    query = ExplicitFakeRagQueryService(
        streams=[
            ["固定\n", "回答"],
            [STREAM_ERROR_RESPONSE],
            ["取" * 120, "不应读取"],
        ]
    )
    repository = RagChatRepository(database.sessions, now=lambda: FIXED_NOW)
    service = RagChatService(
        repository,
        query,
        history_enabled=True,
        history_max_messages=10,
    )

    try:
        with pytest.raises(BusinessException, match="部分知识库不存在"):
            await service.create_session(
                CreateSessionRequest(knowledgeBaseIds=[first_id, 9223372036854775807])
            )

        created = await service.create_session(
            CreateSessionRequest(
                knowledgeBaseIds=[first_id],
                title="rag-chat-integration-session",
            )
        )
        session_id = created.id
        assert created.model_dump(by_alias=True).keys() == {
            "id",
            "title",
            "knowledgeBaseIds",
            "createdAt",
        }

        select_count = 0

        def count_selects(
            _connection: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: object,
        ) -> None:
            nonlocal select_count
            if statement.lstrip().upper().startswith("SELECT"):
                select_count += 1

        event.listen(database.engine.sync_engine, "before_cursor_execute", count_selects)
        try:
            listed = await service.list_sessions()
            assert any(item.id == session_id for item in listed)
            assert select_count == 2
            select_count = 0
            detail = await service.session_detail(session_id)
            assert select_count == 2
        finally:
            event.remove(database.engine.sync_engine, "before_cursor_execute", count_selects)
        assert [item.id for item in detail.knowledge_bases] == [first_id]
        assert detail.messages == []

        await service.update_title(session_id, "rag-chat-integration-updated")
        await service.toggle_pin(session_id)
        await service.update_knowledge_bases(
            session_id,
            [second_id, 9223372036854775807],
        )
        updated = await service.session_detail(session_id)
        assert updated.title == "rag-chat-integration-updated"
        assert [item.id for item in updated.knowledge_bases] == [second_id]
        listed_session = next(
            item for item in await service.list_sessions() if item.id == session_id
        )
        assert listed_session.is_pinned

        normal_message_id = await service.prepare_stream_message(session_id, "第一问")
        normal_chunks = await service.get_stream_answer(session_id, "第一问")
        normal_body = [
            chunk
            async for chunk in rag_chat_sse_stream(
                service,
                normal_message_id,
                normal_chunks,
            )
        ]
        assert normal_body == [
            b"data:\xe5\x9b\xba\xe5\xae\x9a\\n\n\n",
            (b"data:\xe5\x9b\x9e\xe7\xad\x94\n\n"),
        ]

        error_message_id = await service.prepare_stream_message(session_id, "第二问")
        error_chunks = await service.get_stream_answer(session_id, "第二问")
        assert [
            chunk
            async for chunk in rag_chat_sse_stream(
                service,
                error_message_id,
                error_chunks,
            )
        ] == [f"data:{STREAM_ERROR_RESPONSE}\n\n".encode()]

        cancelled_message_id = await service.prepare_stream_message(session_id, "第三问")
        cancelled_chunks = await service.get_stream_answer(session_id, "第三问")
        cancelled_body = rag_chat_sse_stream(
            service,
            cancelled_message_id,
            cancelled_chunks,
        )
        assert await anext(cancelled_body) == f"data:{'取' * 120}\n\n".encode()
        await cancelled_body.aclose()

        detail = await service.session_detail(session_id)
        assert [(message.type, message.content) for message in detail.messages] == [
            ("user", "第一问"),
            ("assistant", "固定\n回答"),
            ("user", "第二问"),
            ("assistant", STREAM_ERROR_RESPONSE),
            ("user", "第三问"),
            ("assistant", ""),
        ]
        async with database.sessions() as verification:
            incomplete = await verification.scalar(
                select(RagChatMessage).where(
                    RagChatMessage.id == cancelled_message_id,
                    RagChatMessage.completed.is_(False),
                )
            )
            assert incomplete is not None
            message_count = await verification.scalar(
                select(func.count())
                .select_from(RagChatMessage)
                .where(RagChatMessage.session_id == session_id)
            )
            assert message_count == 6
        assert query.calls[0][2] == []
        assert query.calls[1][2] == [
            {"role": "user", "content": "第一问"},
            {"role": "assistant", "content": "固定\n回答"},
        ]
        assert query.closed == 3
        assert await redis.xrange(KB_VECTORIZE.key) == []

        await service.delete_session(session_id)
        with pytest.raises(BusinessException, match="会话不存在"):
            await service.session_detail(session_id)
    finally:
        await cleanup(database)
        await redis.delete(KB_VECTORIZE.key)
        await redis.aclose()
        await database.close()
