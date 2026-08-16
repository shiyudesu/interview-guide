from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from sqlalchemy import BigInteger, delete, func, or_, select, update
from sqlalchemy import cast as sql_cast
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def increment_question_counts(self, knowledge_base_ids: list[int]) -> None:
        unique_ids: list[int] = list(dict.fromkeys(knowledge_base_ids))
        if not unique_ids:
            return
        existing_ids = set(
            await self._session.scalars(
                select(KnowledgeBase.id).where(KnowledgeBase.id.in_(unique_ids))
            )
        )
        for knowledge_base_id in unique_ids:
            if knowledge_base_id not in existing_ids:
                raise BusinessException(
                    ErrorCode.NOT_FOUND,
                    f"知识库不存在: {knowledge_base_id}",
                )
        await self._session.execute(
            update(KnowledgeBase)
            .where(KnowledgeBase.id.in_(unique_ids))
            .values(question_count=KnowledgeBase.question_count + 1)
        )
