from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_guide.common.db.models import KnowledgeBase, KnowledgeBaseQuestion


@dataclass(frozen=True)
class QuestionRow:
    question: KnowledgeBaseQuestion
    knowledge_base_name: str | None


@dataclass(frozen=True)
class StoredCategoryCount:
    category: str
    count: int


class KnowledgeBaseQuestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def knowledge_base(
        self,
        knowledge_base_id: int,
        *,
        for_update: bool = False,
    ) -> KnowledgeBase | None:
        statement = select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
        if for_update:
            statement = statement.with_for_update()
        return cast(KnowledgeBase | None, await self._session.scalar(statement))

    async def question(
        self,
        question_id: int,
    ) -> QuestionRow | None:
        row = (
            await self._session.execute(
                select(KnowledgeBaseQuestion, KnowledgeBase.name)
                .outerjoin(
                    KnowledgeBase,
                    KnowledgeBase.id == KnowledgeBaseQuestion.knowledge_base_id,
                )
                .where(KnowledgeBaseQuestion.id == question_id)
            )
        ).first()
        return QuestionRow(row[0], row[1]) if row is not None else None

    async def list_questions(
        self,
        knowledge_base_id: int,
        status: str | None = None,
    ) -> list[QuestionRow]:
        statement = (
            select(KnowledgeBaseQuestion, KnowledgeBase.name)
            .outerjoin(
                KnowledgeBase,
                KnowledgeBase.id == KnowledgeBaseQuestion.knowledge_base_id,
            )
            .where(KnowledgeBaseQuestion.knowledge_base_id == knowledge_base_id)
        )
        if status is not None:
            statement = statement.where(KnowledgeBaseQuestion.status == status)
        rows = await self._session.execute(
            statement.order_by(KnowledgeBaseQuestion.updated_at.desc())
        )
        return [QuestionRow(row[0], row[1]) for row in rows]

    async def categories(self, knowledge_base_id: int) -> list[StoredCategoryCount]:
        rows = await self._session.execute(
            select(
                KnowledgeBaseQuestion.category,
                func.count(KnowledgeBaseQuestion.id),
            )
            .where(
                KnowledgeBaseQuestion.knowledge_base_id == knowledge_base_id,
                KnowledgeBaseQuestion.category.is_not(None),
                KnowledgeBaseQuestion.category != "",
            )
            .group_by(KnowledgeBaseQuestion.category)
            .order_by(
                func.count(KnowledgeBaseQuestion.id).desc(),
                KnowledgeBaseQuestion.category.asc(),
            )
        )
        return [
            StoredCategoryCount(str(category), int(count))
            for category, count in rows
            if category is not None
        ]

    async def active_questions(
        self,
        knowledge_base_id: int,
        difficulty: str,
        category: str | None,
    ) -> list[KnowledgeBaseQuestion]:
        statement = select(KnowledgeBaseQuestion).where(
            KnowledgeBaseQuestion.knowledge_base_id == knowledge_base_id,
            KnowledgeBaseQuestion.difficulty == difficulty,
            KnowledgeBaseQuestion.status == "ACTIVE",
        )
        if category is not None:
            statement = statement.where(KnowledgeBaseQuestion.category == category)
        result = await self._session.scalars(
            statement.order_by(KnowledgeBaseQuestion.updated_at.desc())
        )
        return list(result)

    async def recent_questions(
        self,
        knowledge_base_id: int,
        difficulty: str,
        limit: int = 20,
    ) -> list[KnowledgeBaseQuestion]:
        result = await self._session.scalars(
            select(KnowledgeBaseQuestion)
            .where(
                KnowledgeBaseQuestion.knowledge_base_id == knowledge_base_id,
                KnowledgeBaseQuestion.difficulty == difficulty,
            )
            .order_by(KnowledgeBaseQuestion.updated_at.desc())
            .limit(limit)
        )
        return list(result)

    async def stale_generation_tasks(
        self,
        status: str,
        threshold: datetime,
    ) -> list[tuple[int, str | None]]:
        rows = await self._session.execute(
            select(KnowledgeBase.id, KnowledgeBase.question_gen_task_id).where(
                KnowledgeBase.question_gen_status == status,
                (
                    KnowledgeBase.question_gen_updated_at.is_(None)
                    | (KnowledgeBase.question_gen_updated_at < threshold)
                ),
            )
        )
        return [(int(knowledge_base_id), task_id) for knowledge_base_id, task_id in rows]

    async def add(self, question: KnowledgeBaseQuestion) -> KnowledgeBaseQuestion:
        self._session.add(question)
        await self._session.flush()
        return question

    async def delete_question(self, question: KnowledgeBaseQuestion) -> None:
        await self._session.delete(question)

    async def replace_questions(
        self,
        knowledge_base_id: int,
        questions: list[KnowledgeBaseQuestion],
    ) -> None:
        await self._session.execute(
            delete(KnowledgeBaseQuestion).where(
                KnowledgeBaseQuestion.knowledge_base_id == knowledge_base_id
            )
        )
        self._session.add_all(questions)
        await self._session.flush()
