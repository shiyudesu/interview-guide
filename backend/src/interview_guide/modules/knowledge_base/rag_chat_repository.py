from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.db.models import (
    KnowledgeBase,
    RagChatMessage,
    RagChatSession,
    RagSessionKnowledgeBase,
)
from interview_guide.common.errors import BusinessException, ErrorCode


@dataclass(frozen=True)
class SessionRecord:
    session: RagChatSession
    knowledge_bases: tuple[KnowledgeBase, ...]


@dataclass(frozen=True)
class SessionDetailRecord:
    session: RagChatSession
    knowledge_bases: tuple[KnowledgeBase, ...]
    messages: tuple[RagChatMessage, ...]


@dataclass(frozen=True)
class StreamContext:
    knowledge_base_ids: tuple[int, ...]
    history: tuple[dict[str, str], ...]


class RagChatRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._sessions = sessions
        self._now = now

    async def create_session(
        self,
        knowledge_base_ids: Sequence[int | None],
        title: str | None,
    ) -> SessionRecord:
        async with self._sessions() as session, session.begin():
            knowledge_bases = await self._find_knowledge_bases(session, knowledge_base_ids)
            if len(knowledge_bases) != len(knowledge_base_ids):
                raise BusinessException(ErrorCode.NOT_FOUND, "部分知识库不存在")
            resolved_title = (
                title
                if title is not None and not self._is_blank_excluding_nbsp(title)
                else self._generate_title(knowledge_bases)
            )
            now = self._now()
            entity = RagChatSession(
                created_at=now,
                is_pinned=False,
                message_count=0,
                status="ACTIVE",
                title=resolved_title,
                updated_at=now,
            )
            session.add(entity)
            await session.flush()
            session.add_all(
                RagSessionKnowledgeBase(
                    session_id=entity.id,
                    knowledge_base_id=knowledge_base.id,
                )
                for knowledge_base in knowledge_bases
            )
            await session.flush()
            return SessionRecord(entity, tuple(knowledge_bases))

    async def list_sessions(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[SessionRecord]:
        async with self._sessions() as session:
            statement = select(RagChatSession).order_by(
                RagChatSession.is_pinned.desc(),
                RagChatSession.updated_at.desc(),
            )
            if offset:
                statement = statement.offset(offset)
            if limit is not None:
                statement = statement.limit(limit)
            entities = list(await session.scalars(statement))
            if not entities:
                return []
            rows = await session.execute(
                select(RagSessionKnowledgeBase.session_id, KnowledgeBase)
                .join(
                    KnowledgeBase,
                    KnowledgeBase.id == RagSessionKnowledgeBase.knowledge_base_id,
                )
                .where(RagSessionKnowledgeBase.session_id.in_([entity.id for entity in entities]))
            )
            grouped: defaultdict[int, list[KnowledgeBase]] = defaultdict(list)
            for session_id, knowledge_base in rows:
                grouped[int(session_id)].append(knowledge_base)
            return [SessionRecord(entity, tuple(grouped[entity.id])) for entity in entities]

    async def session_detail(self, session_id: int) -> SessionDetailRecord:
        async with self._sessions() as session:
            rows = list(
                (
                    await session.execute(
                        select(RagChatSession, KnowledgeBase)
                        .outerjoin(
                            RagSessionKnowledgeBase,
                            RagSessionKnowledgeBase.session_id == RagChatSession.id,
                        )
                        .outerjoin(
                            KnowledgeBase,
                            KnowledgeBase.id == RagSessionKnowledgeBase.knowledge_base_id,
                        )
                        .where(RagChatSession.id == session_id)
                    )
                ).all()
            )
            if not rows:
                raise BusinessException(ErrorCode.NOT_FOUND, "会话不存在")
            entity = cast(RagChatSession, rows[0][0])
            knowledge_bases = tuple(
                cast(KnowledgeBase, knowledge_base)
                for _, knowledge_base in rows
                if knowledge_base is not None
            )
            messages = tuple(
                await session.scalars(
                    select(RagChatMessage)
                    .where(RagChatMessage.session_id == session_id)
                    .order_by(RagChatMessage.message_order.asc())
                )
            )
            return SessionDetailRecord(entity, knowledge_bases, messages)

    async def update_title(self, session_id: int, title: str) -> None:
        async with self._sessions() as session, session.begin():
            entity = await self._require_session(session, session_id)
            entity.title = title
            entity.updated_at = self._now()

    async def toggle_pin(self, session_id: int) -> None:
        async with self._sessions() as session, session.begin():
            entity = await self._require_session(session, session_id)
            entity.is_pinned = not (entity.is_pinned or False)
            entity.updated_at = self._now()

    async def update_knowledge_bases(
        self,
        session_id: int,
        knowledge_base_ids: Sequence[int | None],
    ) -> None:
        async with self._sessions() as session, session.begin():
            entity = await self._require_session(session, session_id)
            knowledge_bases = await self._find_knowledge_bases(session, knowledge_base_ids)
            await session.execute(
                delete(RagSessionKnowledgeBase).where(
                    RagSessionKnowledgeBase.session_id == session_id
                )
            )
            session.add_all(
                RagSessionKnowledgeBase(
                    session_id=session_id,
                    knowledge_base_id=knowledge_base.id,
                )
                for knowledge_base in knowledge_bases
            )
            entity.updated_at = self._now()

    async def delete_session(self, session_id: int) -> None:
        async with self._sessions() as session, session.begin():
            entity = await session.get(RagChatSession, session_id)
            if entity is None:
                raise BusinessException(ErrorCode.NOT_FOUND, "会话不存在")
            await session.execute(
                delete(RagSessionKnowledgeBase).where(
                    RagSessionKnowledgeBase.session_id == session_id
                )
            )
            await session.execute(
                delete(RagChatMessage).where(RagChatMessage.session_id == session_id)
            )
            await session.delete(entity)

    async def prepare_stream_message(self, session_id: int, question: str) -> int:
        async with self._sessions() as session, session.begin():
            entity = cast(
                RagChatSession | None,
                await session.scalar(
                    select(RagChatSession).where(RagChatSession.id == session_id).with_for_update()
                ),
            )
            if entity is None:
                raise BusinessException(ErrorCode.NOT_FOUND, "会话不存在")
            next_order = entity.message_count
            if next_order is None:
                raise TypeError("messageCount is null")
            now = self._now()
            user_message = RagChatMessage(
                completed=True,
                content=question,
                created_at=now,
                message_order=next_order,
                type="USER",
                updated_at=now,
                session_id=session_id,
            )
            assistant_message = RagChatMessage(
                completed=False,
                content="",
                created_at=now,
                message_order=next_order + 1,
                type="ASSISTANT",
                updated_at=now,
                session_id=session_id,
            )
            session.add_all((user_message, assistant_message))
            await session.flush()
            entity.message_count = next_order + 2
            entity.updated_at = now
            return assistant_message.id

    async def complete_stream_message(self, message_id: int, content: str) -> None:
        async with self._sessions() as session, session.begin():
            message = await session.get(RagChatMessage, message_id)
            if message is None:
                raise BusinessException(ErrorCode.NOT_FOUND, "消息不存在")
            message.content = content
            message.completed = True
            message.updated_at = self._now()

    async def stream_context(
        self,
        session_id: int,
        *,
        history_enabled: bool,
        history_max_messages: int,
    ) -> StreamContext:
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(
                        RagChatSession.id,
                        RagSessionKnowledgeBase.knowledge_base_id,
                    )
                    .outerjoin(
                        RagSessionKnowledgeBase,
                        RagSessionKnowledgeBase.session_id == RagChatSession.id,
                    )
                    .where(RagChatSession.id == session_id)
                )
            ).all()
            if not rows:
                raise BusinessException(ErrorCode.NOT_FOUND, "会话不存在")
            knowledge_base_ids = tuple(
                int(knowledge_base_id)
                for _, knowledge_base_id in rows
                if knowledge_base_id is not None
            )
            if not history_enabled:
                return StreamContext(knowledge_base_ids, ())
            recent = list(
                await session.scalars(
                    select(RagChatMessage)
                    .where(
                        RagChatMessage.session_id == session_id,
                        RagChatMessage.completed.is_(True),
                    )
                    .order_by(RagChatMessage.message_order.desc())
                    .limit(history_max_messages + 1)
                )
            )
            history_messages = recent[1:] if len(recent) > 1 else []
            history = tuple(
                {
                    "role": "user" if message.type == "USER" else "assistant",
                    "content": message.content,
                }
                for message in reversed(history_messages)
            )
            return StreamContext(knowledge_base_ids, history)

    @staticmethod
    async def _require_session(
        session: AsyncSession,
        session_id: int,
    ) -> RagChatSession:
        entity = await session.get(RagChatSession, session_id)
        if entity is None:
            raise BusinessException(ErrorCode.NOT_FOUND, "会话不存在")
        return entity

    @staticmethod
    async def _find_knowledge_bases(
        session: AsyncSession,
        knowledge_base_ids: Sequence[int | None],
    ) -> list[KnowledgeBase]:
        ids = [value for value in knowledge_base_ids if value is not None]
        if not ids:
            return []
        return list(await session.scalars(select(KnowledgeBase).where(KnowledgeBase.id.in_(ids))))

    @staticmethod
    def _generate_title(knowledge_bases: Sequence[KnowledgeBase]) -> str:
        if not knowledge_bases:
            return "新对话"
        if len(knowledge_bases) == 1:
            return knowledge_bases[0].name
        return f"{len(knowledge_bases)} 个知识库对话"

    @staticmethod
    def _is_blank_excluding_nbsp(value: str) -> bool:
        if not value:
            return True
        return all(character.isspace() and character != "\u00a0" for character in value)
