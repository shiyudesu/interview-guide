from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import Select

from interview_guide.common.db.models import (
    KnowledgeBase,
    RagChatMessage,
    RagChatSession,
    RagSessionKnowledgeBase,
    VectorStore,
)
from interview_guide.common.errors import BusinessException, ErrorCode


@dataclass(frozen=True)
class KnowledgeBaseStatistics:
    total_count: int
    total_question_count: int
    total_access_count: int
    completed_count: int
    processing_count: int


@dataclass(frozen=True)
class VectorSearchHit:
    content: str
    score: float
    knowledge_base_id: int | None = None


class KnowledgeBaseRepository:
    def __init__(self, session: AsyncSession, user_id: UUID | None = None) -> None:
        self._session = session
        self._user_id = user_id

    async def get(self, knowledge_base_id: int) -> KnowledgeBase | None:
        return cast(
            KnowledgeBase | None,
            await self._session.scalar(
                self._owned(select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id))
            ),
        )

    async def get_by_hash(self, file_hash: str) -> KnowledgeBase | None:
        return cast(
            KnowledgeBase | None,
            await self._session.scalar(
                self._owned(select(KnowledgeBase).where(KnowledgeBase.file_hash == file_hash))
            ),
        )

    async def add(self, entity: KnowledgeBase) -> KnowledgeBase:
        if self._user_id is not None:
            entity.user_id = self._user_id
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def list_entities(
        self,
        *,
        vector_status: str | None = None,
        category: str | None = None,
        uncategorized: bool = False,
        ids: list[int] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[KnowledgeBase]:
        statement = select(KnowledgeBase)
        statement = self._owned(statement)
        if vector_status is not None:
            statement = statement.where(KnowledgeBase.vector_status == vector_status)
        if ids is not None:
            statement = statement.where(KnowledgeBase.id.in_(ids))
        if uncategorized:
            statement = statement.where(KnowledgeBase.category.is_(None))
        elif category is not None:
            statement = statement.where(KnowledgeBase.category == category)
        statement = statement.order_by(KnowledgeBase.uploaded_at.desc())
        if offset:
            statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)
        result = await self._session.scalars(statement)
        return list(result)

    async def search(self, keyword: str) -> list[KnowledgeBase]:
        value = f"%{keyword.strip().lower()}%"
        result = await self._session.scalars(
            self._owned(
                select(KnowledgeBase)
                .where(
                    or_(
                        func.lower(KnowledgeBase.name).like(value),
                        func.lower(KnowledgeBase.original_filename).like(value),
                    )
                )
                .order_by(KnowledgeBase.uploaded_at.desc())
            )
        )
        return list(result)

    async def categories(self) -> list[str]:
        result = await self._session.scalars(
            self._owned(select(KnowledgeBase.category))
            .where(KnowledgeBase.category.is_not(None))
            .distinct()
            .order_by(KnowledgeBase.category)
        )
        return cast(list[str], list(result))

    async def statistics(self) -> KnowledgeBaseStatistics:
        total_statement = select(func.count()).select_from(KnowledgeBase)
        access_statement = select(func.coalesce(func.sum(KnowledgeBase.access_count), 0))
        completed_statement = (
            select(func.count())
            .select_from(KnowledgeBase)
            .where(KnowledgeBase.vector_status == "COMPLETED")
        )
        processing_statement = (
            select(func.count())
            .select_from(KnowledgeBase)
            .where(KnowledgeBase.vector_status == "PROCESSING")
        )
        if self._user_id is not None:
            total_statement = total_statement.where(KnowledgeBase.user_id == self._user_id)
            access_statement = access_statement.where(KnowledgeBase.user_id == self._user_id)
            completed_statement = completed_statement.where(KnowledgeBase.user_id == self._user_id)
            processing_statement = processing_statement.where(
                KnowledgeBase.user_id == self._user_id
            )
        total = await self._session.scalar(total_statement)
        message_statement = (
            select(func.count())
            .select_from(RagChatMessage)
            .join(RagChatSession, RagChatSession.id == RagChatMessage.session_id)
            .where(RagChatMessage.type == "USER")
        )
        if self._user_id is not None:
            message_statement = message_statement.where(RagChatSession.user_id == self._user_id)
        user_messages = await self._session.scalar(message_statement)
        access = await self._session.scalar(access_statement)
        completed = await self._session.scalar(completed_statement)
        processing = await self._session.scalar(processing_statement)
        return KnowledgeBaseStatistics(
            total_count=total or 0,
            total_question_count=user_messages or 0,
            total_access_count=access or 0,
            completed_count=completed or 0,
            processing_count=processing or 0,
        )

    async def delete_records(self, knowledge_base_id: int) -> None:
        await self._session.execute(
            delete(RagSessionKnowledgeBase).where(
                RagSessionKnowledgeBase.knowledge_base_id == knowledge_base_id
            )
        )
        statement = delete(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
        if self._user_id is not None:
            statement = statement.where(KnowledgeBase.user_id == self._user_id)
        await self._session.execute(statement)

    async def delete_vectors(self, knowledge_base_id: int) -> None:
        await self._session.execute(
            delete(VectorStore).where(
                VectorStore.metadata_json["kb_id"].astext == str(knowledge_base_id)
            )
        )

    async def increment_question_counts(
        self,
        knowledge_base_ids: Sequence[int],
    ) -> None:
        if not knowledge_base_ids:
            return
        result = await self._session.execute(
            text(
                """
                WITH requested AS (
                    SELECT id, min(ordinality) AS first_ordinal
                    FROM unnest(CAST(:ids AS bigint[]))
                        WITH ORDINALITY AS input(id, ordinality)
                    GROUP BY id
                ),
                updated AS (
                    UPDATE knowledge_bases AS knowledge_base
                    SET question_count = knowledge_base.question_count + 1
                    FROM requested
                    WHERE knowledge_base.id = requested.id
                      AND (
                        CAST(:user_id AS uuid) IS NULL
                        OR knowledge_base.user_id = CAST(:user_id AS uuid)
                      )
                    RETURNING knowledge_base.id
                )
                SELECT requested.id
                FROM requested
                LEFT JOIN updated ON updated.id = requested.id
                WHERE updated.id IS NULL
                ORDER BY requested.first_ordinal
                LIMIT 1
                """
            ),
            {
                "ids": list(knowledge_base_ids),
                "user_id": str(self._user_id) if self._user_id is not None else None,
            },
        )
        missing_id = result.scalar_one_or_none()
        if missing_id is not None:
            raise BusinessException(
                ErrorCode.NOT_FOUND,
                f"知识库不存在: {missing_id}",
            )

    async def knowledge_base_names(
        self,
        knowledge_base_ids: Sequence[int],
    ) -> list[str]:
        unique_ids = list(dict.fromkeys(knowledge_base_ids))
        rows = await self._session.execute(
            self._owned(
                select(KnowledgeBase.id, KnowledgeBase.name).where(KnowledgeBase.id.in_(unique_ids))
            )
        )
        names = {int(knowledge_base_id): name for knowledge_base_id, name in rows}
        return [
            names.get(knowledge_base_id, "未知知识库") for knowledge_base_id in knowledge_base_ids
        ]

    async def similarity_search(
        self,
        knowledge_base_ids: Sequence[int],
        embedding: Sequence[float],
        top_k: int,
        min_score: float,
    ) -> list[VectorSearchHit]:
        result = await self._session.execute(
            text(
                """
                SELECT
                    content,
                    1 - (embedding <=> CAST(:embedding AS vector)) AS score,
                    metadata->>'kb_id' AS knowledge_base_id
                FROM vector_store
                WHERE metadata->>'kb_id' = ANY(CAST(:knowledge_base_ids AS text[]))
                  AND (
                      CAST(:user_id AS uuid) IS NULL
                      OR EXISTS (
                          SELECT 1 FROM knowledge_bases AS knowledge_base
                          WHERE knowledge_base.id = CAST(metadata->>'kb_id' AS bigint)
                            AND knowledge_base.user_id = CAST(:user_id AS uuid)
                      )
                  )
                  AND embedding IS NOT NULL
                  AND (
                      :min_score <= 0
                      OR 1 - (embedding <=> CAST(:embedding AS vector)) >= :min_score
                  )
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
                """
            ),
            {
                "embedding": "[" + ",".join(str(float(value)) for value in embedding) + "]",
                "knowledge_base_ids": [str(value) for value in knowledge_base_ids],
                "min_score": min_score,
                "top_k": max(top_k, 1),
                "user_id": str(self._user_id) if self._user_id is not None else None,
            },
        )
        return [
            VectorSearchHit(
                content=str(content),
                score=float(score),
                knowledge_base_id=self._parse_knowledge_base_id(knowledge_base_id),
            )
            for content, score, knowledge_base_id in result
            if content is not None
        ]

    async def similarity_search_unfiltered(
        self,
        embedding: Sequence[float],
        top_k: int,
        min_score: float,
    ) -> list[VectorSearchHit]:
        result = await self._session.execute(
            text(
                """
                SELECT
                    content,
                    1 - (embedding <=> CAST(:embedding AS vector)) AS score,
                    metadata->>'kb_id' AS knowledge_base_id
                FROM vector_store
                WHERE embedding IS NOT NULL
                  AND (
                      CAST(:user_id AS uuid) IS NULL
                      OR EXISTS (
                          SELECT 1 FROM knowledge_bases AS knowledge_base
                          WHERE knowledge_base.id = CAST(metadata->>'kb_id' AS bigint)
                            AND knowledge_base.user_id = CAST(:user_id AS uuid)
                      )
                  )
                  AND (
                      :min_score <= 0
                      OR 1 - (embedding <=> CAST(:embedding AS vector)) >= :min_score
                  )
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
                """
            ),
            {
                "embedding": "[" + ",".join(str(float(value)) for value in embedding) + "]",
                "min_score": min_score,
                "top_k": max(top_k, 1),
                "user_id": str(self._user_id) if self._user_id is not None else None,
            },
        )
        return [
            VectorSearchHit(
                content=str(content),
                score=float(score),
                knowledge_base_id=self._parse_knowledge_base_id(knowledge_base_id),
            )
            for content, score, knowledge_base_id in result
            if content is not None
        ]

    @staticmethod
    def _parse_knowledge_base_id(value: object) -> int | None:
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None

    def _owned(self, statement: Select[Any]) -> Select[Any]:
        if self._user_id is None:
            return statement
        return statement.where(KnowledgeBase.user_id == self._user_id)


class KnowledgeBaseQueryRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        user_id: UUID | None = None,
    ) -> None:
        self._sessions = sessions
        self._user_id = user_id

    async def increment_question_counts(
        self,
        knowledge_base_ids: Sequence[int],
    ) -> None:
        async with self._sessions() as session, session.begin():
            await KnowledgeBaseRepository(session, self._user_id).increment_question_counts(
                knowledge_base_ids
            )

    async def knowledge_base_names(
        self,
        knowledge_base_ids: Sequence[int],
    ) -> list[str]:
        async with self._sessions() as session:
            return await KnowledgeBaseRepository(session, self._user_id).knowledge_base_names(
                knowledge_base_ids
            )

    async def similarity_search(
        self,
        knowledge_base_ids: Sequence[int],
        embedding: Sequence[float],
        top_k: int,
        min_score: float,
    ) -> list[VectorSearchHit]:
        async with self._sessions() as session:
            return await KnowledgeBaseRepository(session, self._user_id).similarity_search(
                knowledge_base_ids,
                embedding,
                top_k,
                min_score,
            )

    async def similarity_search_unfiltered(
        self,
        embedding: Sequence[float],
        top_k: int,
        min_score: float,
    ) -> list[VectorSearchHit]:
        async with self._sessions() as session:
            return await KnowledgeBaseRepository(
                session, self._user_id
            ).similarity_search_unfiltered(
                embedding,
                top_k,
                min_score,
            )
