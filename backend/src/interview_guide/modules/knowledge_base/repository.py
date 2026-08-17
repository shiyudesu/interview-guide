from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from sqlalchemy import BigInteger, delete, func, or_, select, text
from sqlalchemy import cast as sql_cast
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.db.models import (
    KnowledgeBase,
    RagChatMessage,
    RagSessionKnowledgeBase,
    VectorStore,
)
from interview_guide.common.errors import BusinessException, ErrorCode


def java_trim(value: str) -> str:
    start = 0
    end = len(value)
    while start < end and ord(value[start]) <= 0x20:
        start += 1
    while end > start and ord(value[end - 1]) <= 0x20:
        end -= 1
    return value[start:end]


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
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, knowledge_base_id: int) -> KnowledgeBase | None:
        return cast(
            KnowledgeBase | None,
            await self._session.get(KnowledgeBase, knowledge_base_id),
        )

    async def get_by_hash(self, file_hash: str) -> KnowledgeBase | None:
        return cast(
            KnowledgeBase | None,
            await self._session.scalar(
                select(KnowledgeBase).where(KnowledgeBase.file_hash == file_hash)
            ),
        )

    async def add(self, entity: KnowledgeBase) -> KnowledgeBase:
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def list_entities(
        self,
        *,
        vector_status: str | None = None,
        category: str | None = None,
        uncategorized: bool = False,
    ) -> list[KnowledgeBase]:
        statement = select(KnowledgeBase)
        if vector_status is not None:
            statement = statement.where(KnowledgeBase.vector_status == vector_status)
        if uncategorized:
            statement = statement.where(KnowledgeBase.category.is_(None))
        elif category is not None:
            statement = statement.where(KnowledgeBase.category == category)
        result = await self._session.scalars(statement.order_by(KnowledgeBase.uploaded_at.desc()))
        return list(result)

    async def search(self, keyword: str) -> list[KnowledgeBase]:
        value = f"%{java_trim(keyword).lower()}%"
        result = await self._session.scalars(
            select(KnowledgeBase)
            .where(
                or_(
                    func.lower(KnowledgeBase.name).like(value),
                    func.lower(KnowledgeBase.original_filename).like(value),
                )
            )
            .order_by(KnowledgeBase.uploaded_at.desc())
        )
        return list(result)

    async def categories(self) -> list[str]:
        result = await self._session.scalars(
            select(KnowledgeBase.category)
            .where(KnowledgeBase.category.is_not(None))
            .distinct()
            .order_by(KnowledgeBase.category)
        )
        return cast(list[str], list(result))

    async def statistics(self) -> KnowledgeBaseStatistics:
        total = await self._session.scalar(select(func.count()).select_from(KnowledgeBase))
        user_messages = await self._session.scalar(
            select(func.count()).select_from(RagChatMessage).where(RagChatMessage.type == "USER")
        )
        access = await self._session.scalar(
            select(func.coalesce(func.sum(KnowledgeBase.access_count), 0))
        )
        completed = await self._session.scalar(
            select(func.count())
            .select_from(KnowledgeBase)
            .where(KnowledgeBase.vector_status == "COMPLETED")
        )
        processing = await self._session.scalar(
            select(func.count())
            .select_from(KnowledgeBase)
            .where(KnowledgeBase.vector_status == "PROCESSING")
        )
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
        await self._session.execute(
            delete(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
        )

    async def delete_vectors(self, knowledge_base_id: int) -> None:
        await self._session.execute(
            delete(VectorStore).where(
                (VectorStore.metadata_json["kb_id"].astext == str(knowledge_base_id))
                | (
                    VectorStore.metadata_json["kb_id_long"].astext.is_not(None)
                    & (
                        sql_cast(
                            VectorStore.metadata_json["kb_id_long"].astext,
                            BigInteger,
                        )
                        == knowledge_base_id
                    )
                )
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
            {"ids": list(knowledge_base_ids)},
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
            select(KnowledgeBase.id, KnowledgeBase.name).where(KnowledgeBase.id.in_(unique_ids))
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


class KnowledgeBaseQueryRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
    ) -> None:
        self._sessions = sessions

    async def increment_question_counts(
        self,
        knowledge_base_ids: Sequence[int],
    ) -> None:
        async with self._sessions() as session, session.begin():
            await KnowledgeBaseRepository(session).increment_question_counts(knowledge_base_ids)

    async def knowledge_base_names(
        self,
        knowledge_base_ids: Sequence[int],
    ) -> list[str]:
        async with self._sessions() as session:
            return await KnowledgeBaseRepository(session).knowledge_base_names(knowledge_base_ids)

    async def similarity_search(
        self,
        knowledge_base_ids: Sequence[int],
        embedding: Sequence[float],
        top_k: int,
        min_score: float,
    ) -> list[VectorSearchHit]:
        async with self._sessions() as session:
            return await KnowledgeBaseRepository(session).similarity_search(
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
            return await KnowledgeBaseRepository(session).similarity_search_unfiltered(
                embedding,
                top_k,
                min_score,
            )
