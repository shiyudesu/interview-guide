from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.db.models import LEGACY_OWNER_ID, KnowledgeBase
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.redis.streams import (
    FIELD_CONTENT,
    FIELD_KB_ID,
    FIELD_RETRY_COUNT,
    KB_VECTORIZE,
)
from interview_guide.infrastructure.export.pdf import original_file_download_headers
from interview_guide.infrastructure.file.content_type import ContentTypeDetector
from interview_guide.infrastructure.file.hash import sha256_bytes
from interview_guide.infrastructure.file.validation import (
    KNOWLEDGE_BASE_MAX_BYTES,
    is_knowledge_base_mime_type,
    is_markdown_extension,
    validate_content_type,
    validate_file,
)
from interview_guide.modules.knowledge_base.repository import KnowledgeBaseRepository

logger = logging.getLogger(__name__)


class KnowledgeBaseStorage(Protocol):
    async def upload(
        self,
        data: bytes,
        original_filename: str | None,
        content_type: str | None,
        prefix: str,
    ) -> str: ...

    async def download(self, key: str) -> bytes: ...

    async def delete(self, key: str | None) -> None: ...

    def object_url(self, key: str) -> str: ...


class KnowledgeBaseDocumentParser(Protocol):
    async def parse(
        self,
        data: bytes,
        filename: str | None,
        content_type: str | None,
    ) -> str: ...


class KnowledgeBaseStreams(Protocol):
    async def add(
        self,
        stream_key: str,
        fields: dict[str, str],
        *,
        max_len: int = 1000,
        message_id: str = "*",
    ) -> str: ...


def is_blank_text(value: str | None) -> bool:
    return value is None or not value or value.isspace()


def item(entity: KnowledgeBase) -> dict[str, Any]:
    return {
        "id": entity.id,
        "name": entity.name,
        "category": entity.category,
        "originalFilename": entity.original_filename,
        "fileSize": entity.file_size,
        "contentType": entity.content_type,
        "uploadedAt": entity.uploaded_at,
        "lastAccessedAt": entity.last_accessed_at,
        "accessCount": entity.access_count,
        "questionCount": entity.question_count,
        "vectorStatus": entity.vector_status,
        "vectorError": entity.vector_error,
        "chunkCount": entity.chunk_count,
        "questionGenStatus": entity.question_gen_status,
        "questionGenError": entity.question_gen_error,
    }


class KnowledgeBaseService:
    def __init__(
        self,
        session: AsyncSession,
        sessions: async_sessionmaker[AsyncSession],
        storage: KnowledgeBaseStorage,
        streams: KnowledgeBaseStreams,
        parser: KnowledgeBaseDocumentParser,
        now: Callable[[], datetime] = datetime.now,
        user_id: UUID | None = None,
    ) -> None:
        self._session = session
        self._sessions = sessions
        self._user_id = user_id or LEGACY_OWNER_ID
        self._repository = KnowledgeBaseRepository(session, self._user_id)
        self._storage = storage
        self._streams = streams
        self._parser = parser
        self._now = now

    async def list_items(
        self,
        vector_status: str | None,
        sort_by: str | None,
        *,
        ids: list[int] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        custom_sort = bool(sort_by and sort_by.lower() in {"size", "access", "question"})
        entities = await self._repository.list_entities(
            vector_status=vector_status,
            ids=ids,
            limit=None if custom_sort else limit,
            offset=0 if custom_sort else offset,
        )
        if custom_sort:
            assert sort_by is not None
            field = {
                "size": lambda value: value.file_size or 0,
                "access": lambda value: value.access_count or 0,
                "question": lambda value: value.question_count or 0,
            }[sort_by.lower()]
            entities.sort(key=field, reverse=True)
            end = offset + limit if limit is not None else None
            entities = entities[offset:end]
        return [item(entity) for entity in entities]

    async def detail(self, knowledge_base_id: int) -> dict[str, Any] | None:
        entity = await self._repository.get(knowledge_base_id)
        return item(entity) if entity is not None else None

    async def categories(self) -> list[str]:
        return await self._repository.categories()

    async def list_by_category(self, category: str | None) -> list[dict[str, Any]]:
        blank = is_blank_text(category)
        entities = await self._repository.list_entities(
            category=category if not blank else None,
            uncategorized=blank,
        )
        return [item(entity) for entity in entities]

    async def search(self, keyword: str) -> list[dict[str, Any]]:
        entities = (
            await self._repository.list_entities()
            if is_blank_text(keyword)
            else await self._repository.search(keyword)
        )
        return [item(entity) for entity in entities]

    async def statistics(self) -> dict[str, int]:
        statistics = await self._repository.statistics()
        return {
            "totalCount": statistics.total_count,
            "totalQuestionCount": statistics.total_question_count,
            "totalAccessCount": statistics.total_access_count,
            "completedCount": statistics.completed_count,
            "processingCount": statistics.processing_count,
        }

    async def update_category(
        self,
        knowledge_base_id: int,
        category: str | None,
    ) -> None:
        entity = await self._repository.get(knowledge_base_id)
        if entity is None:
            raise BusinessException(
                ErrorCode.KNOWLEDGE_BASE_NOT_FOUND,
                "知识库不存在",
            )
        entity.category = category if not is_blank_text(category) else None
        await self._session.commit()

    async def upload(
        self,
        data: bytes,
        filename: str | None,
        upload_content_type: str | None,
        name: str | None,
        category: str | None,
    ) -> dict[str, object]:
        validate_file(data, KNOWLEDGE_BASE_MAX_BYTES, "知识库")
        detected_type = ContentTypeDetector().detect(
            data,
            filename,
            upload_content_type,
        )
        validate_content_type(
            detected_type,
            filename,
            is_knowledge_base_mime_type,
            is_markdown_extension,
            f"不支持的文件类型: {detected_type}，支持的类型：PDF、DOCX、DOC、TXT、MD等",
        )
        file_hash = sha256_bytes(data)
        existing = await self._repository.get_by_hash(file_hash)
        if existing is not None:
            existing.access_count = (existing.access_count or 0) + 1
            existing.last_accessed_at = self._now()
            await self._session.commit()
            return {
                "knowledgeBase": {
                    "id": existing.id,
                    "name": existing.name,
                    "fileSize": existing.file_size,
                    "contentLength": 0,
                },
                "storage": {
                    "fileKey": existing.storage_key or "",
                    "fileUrl": existing.storage_url or "",
                },
                "duplicate": True,
            }
        await self._session.rollback()
        content = await self._parser.parse(data, filename, detected_type)
        if not content.strip():
            raise BusinessException(
                ErrorCode.INTERNAL_ERROR,
                "无法从文件中提取文本内容，请确保文件格式正确",
            )
        file_key = await self._storage.upload(
            data,
            filename,
            upload_content_type,
            "knowledgebases",
        )
        file_url = self._storage.object_url(file_key)
        uploaded_at = self._now()
        resolved_filename = filename or ""
        knowledge_name = (
            name
            if name is not None and name.strip()
            else resolved_filename.rsplit(".", 1)[0]
            if "." in resolved_filename
            else resolved_filename or "未命名知识库"
        )
        async with self._session.begin():
            entity = await self._repository.add(
                KnowledgeBase(
                    access_count=1,
                    category=category.strip()
                    if category is not None and category.strip()
                    else None,
                    chunk_count=0,
                    content_type=upload_content_type,
                    file_hash=file_hash,
                    file_size=len(data),
                    last_accessed_at=uploaded_at,
                    name=knowledge_name,
                    original_filename=resolved_filename,
                    question_count=0,
                    storage_key=file_key,
                    storage_url=file_url,
                    uploaded_at=uploaded_at,
                    vector_error=None,
                    vector_status="PENDING",
                    user_id=self._user_id,
                )
            )
        await self._enqueue_vectorization(entity.id, content)
        return {
            "knowledgeBase": {
                "id": entity.id,
                "name": entity.name,
                "category": entity.category or "",
                "fileSize": entity.file_size,
                "contentLength": len(content),
                "vectorStatus": "PENDING",
            },
            "storage": {"fileKey": file_key, "fileUrl": file_url},
            "duplicate": False,
        }

    async def download(
        self,
        knowledge_base_id: int,
    ) -> tuple[bytes, dict[str, str]]:
        entity = await self._repository.get(knowledge_base_id)
        if entity is None:
            raise BusinessException(
                ErrorCode.KNOWLEDGE_BASE_NOT_FOUND,
                "知识库不存在",
            )
        if not entity.storage_key:
            raise BusinessException(
                ErrorCode.STORAGE_DOWNLOAD_FAILED,
                "文件存储信息不存在",
            )
        content = await self._storage.download(entity.storage_key)
        return (
            content,
            original_file_download_headers(
                entity.original_filename,
                entity.content_type,
            ),
        )

    async def revectorize(self, knowledge_base_id: int) -> None:
        entity = await self._repository.get(knowledge_base_id)
        if entity is None:
            raise BusinessException(ErrorCode.NOT_FOUND, "知识库不存在")
        storage_key = entity.storage_key
        filename = entity.original_filename
        content_type = entity.content_type
        await self._session.rollback()
        if not storage_key:
            raise BusinessException(
                ErrorCode.STORAGE_DOWNLOAD_FAILED,
                f"文件不存在: {storage_key}",
            )
        data = await self._storage.download(storage_key)
        detected_type = ContentTypeDetector().detect(data, filename, content_type)
        content = await self._parser.parse(data, filename, detected_type)
        if not content.strip():
            raise BusinessException(
                ErrorCode.INTERNAL_ERROR,
                "无法从文件中提取文本内容",
            )
        async with self._session.begin():
            stored = await self._repository.get(knowledge_base_id)
            if stored is None:
                raise BusinessException(ErrorCode.NOT_FOUND, "知识库不存在")
            stored.vector_status = "PENDING"
            stored.vector_error = None
        await self._enqueue_vectorization(knowledge_base_id, content)

    async def delete(self, knowledge_base_id: int) -> None:
        storage_key = await self._delete_database_records(knowledge_base_id)
        try:
            await self._delete_vectors(knowledge_base_id)
        except Exception:
            logger.warning(
                "vector delete failed; continuing storage delete kbId=%s",
                knowledge_base_id,
                exc_info=True,
            )
        try:
            await self._storage.delete(storage_key)
        except Exception:
            logger.warning(
                "storage delete failed after database delete kbId=%s storageKey=%s",
                knowledge_base_id,
                storage_key,
                exc_info=True,
            )

    async def _delete_database_records(
        self,
        knowledge_base_id: int,
    ) -> str | None:
        entity = await self._repository.get(knowledge_base_id)
        if entity is None:
            raise BusinessException(ErrorCode.NOT_FOUND, "知识库不存在")
        storage_key = entity.storage_key
        await self._session.rollback()
        async with self._session.begin():
            await self._repository.delete_records(knowledge_base_id)
        return storage_key

    async def _delete_vectors(self, knowledge_base_id: int) -> None:
        async with self._sessions() as vector_session, vector_session.begin():
            await KnowledgeBaseRepository(
                vector_session,
                self._user_id,
            ).delete_vectors(knowledge_base_id)

    async def update_question_counts(
        self,
        knowledge_base_ids: Sequence[int] | None,
    ) -> None:
        if not knowledge_base_ids:
            return
        await self._session.rollback()
        async with self._session.begin():
            await self._repository.increment_question_counts(list(knowledge_base_ids))

    async def _enqueue_vectorization(
        self,
        knowledge_base_id: int,
        content: str,
    ) -> None:
        try:
            await self._streams.add(
                KB_VECTORIZE.key,
                {
                    FIELD_KB_ID: str(knowledge_base_id),
                    FIELD_CONTENT: content,
                    FIELD_RETRY_COUNT: "0",
                },
            )
        except Exception as error:
            async with self._sessions() as session, session.begin():
                stored = await session.get(KnowledgeBase, knowledge_base_id)
                if stored is not None:
                    stored.vector_status = "FAILED"
                    stored.vector_error = f"任务入队失败: {error}"[:500]
