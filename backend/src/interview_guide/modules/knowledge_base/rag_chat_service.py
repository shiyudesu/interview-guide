from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from interview_guide.common.db.models import KnowledgeBase, RagChatMessage
from interview_guide.modules.knowledge_base.rag_chat_models import (
    CreateSessionRequest,
    KnowledgeBaseListItemDTO,
    MessageDTO,
    SessionDetailDTO,
    SessionDTO,
    SessionListItemDTO,
)
from interview_guide.modules.knowledge_base.rag_chat_repository import (
    RagChatRepository,
    SessionRecord,
)


class RagQueryService(Protocol):
    async def answer_question_stream(
        self,
        knowledge_base_ids: Sequence[int | None] | None,
        question: str | None,
        history: Sequence[dict[str, str]] | None = None,
    ) -> AsyncIterator[str]: ...


class RagChatService:
    def __init__(
        self,
        repository: RagChatRepository,
        query_service: RagQueryService,
        *,
        history_enabled: bool,
        history_max_messages: int,
    ) -> None:
        self._repository = repository
        self._query_service = query_service
        self._history_enabled = history_enabled
        self._history_max_messages = history_max_messages

    async def create_session(self, request: CreateSessionRequest) -> SessionDTO:
        record = await self._repository.create_session(
            request.knowledge_base_ids,
            request.title,
        )
        return self._session_dto(record)

    async def list_sessions(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[SessionListItemDTO]:
        return [
            SessionListItemDTO(
                id=record.session.id,
                title=record.session.title,
                message_count=record.session.message_count,
                knowledge_base_names=[
                    knowledge_base.name for knowledge_base in record.knowledge_bases
                ],
                updated_at=record.session.updated_at,
                is_pinned=record.session.is_pinned or False,
            )
            for record in await self._repository.list_sessions(limit=limit, offset=offset)
        ]

    async def session_detail(self, session_id: int) -> SessionDetailDTO:
        record = await self._repository.session_detail(session_id)
        return SessionDetailDTO(
            id=record.session.id,
            title=record.session.title,
            knowledge_bases=[
                self._knowledge_base_dto(knowledge_base)
                for knowledge_base in record.knowledge_bases
            ],
            messages=[self._message_dto(message) for message in record.messages],
            created_at=record.session.created_at,
            updated_at=record.session.updated_at,
        )

    async def update_title(self, session_id: int, title: str) -> None:
        await self._repository.update_title(session_id, title)

    async def toggle_pin(self, session_id: int) -> None:
        await self._repository.toggle_pin(session_id)

    async def update_knowledge_bases(
        self,
        session_id: int,
        knowledge_base_ids: Sequence[int | None],
    ) -> None:
        await self._repository.update_knowledge_bases(
            session_id,
            knowledge_base_ids,
        )

    async def delete_session(self, session_id: int) -> None:
        await self._repository.delete_session(session_id)

    async def prepare_stream_message(self, session_id: int, question: str) -> int:
        return await self._repository.prepare_stream_message(session_id, question)

    async def get_stream_answer(
        self,
        session_id: int,
        question: str,
    ) -> AsyncIterator[str]:
        context = await self._repository.stream_context(
            session_id,
            history_enabled=self._history_enabled,
            history_max_messages=self._history_max_messages,
        )
        return await self._query_service.answer_question_stream(
            context.knowledge_base_ids,
            question,
            context.history,
        )

    async def complete_stream_message(self, message_id: int, content: str) -> None:
        await self._repository.complete_stream_message(message_id, content)

    @staticmethod
    def _session_dto(record: SessionRecord) -> SessionDTO:
        return SessionDTO(
            id=record.session.id,
            title=record.session.title,
            knowledge_base_ids=[knowledge_base.id for knowledge_base in record.knowledge_bases],
            created_at=record.session.created_at,
        )

    @staticmethod
    def _knowledge_base_dto(
        entity: KnowledgeBase,
    ) -> KnowledgeBaseListItemDTO:
        return KnowledgeBaseListItemDTO(
            id=entity.id,
            name=entity.name,
            category=entity.category,
            original_filename=entity.original_filename,
            file_size=entity.file_size,
            content_type=entity.content_type,
            uploaded_at=entity.uploaded_at,
            last_accessed_at=entity.last_accessed_at,
            access_count=entity.access_count,
            question_count=entity.question_count,
            vector_status=entity.vector_status,
            vector_error=entity.vector_error,
            chunk_count=entity.chunk_count,
            question_gen_status=entity.question_gen_status,
            question_gen_error=entity.question_gen_error,
        )

    @staticmethod
    def _message_dto(entity: RagChatMessage) -> MessageDTO:
        return MessageDTO(
            id=entity.id,
            type=entity.type.lower(),
            content=entity.content,
            created_at=entity.created_at,
        )
