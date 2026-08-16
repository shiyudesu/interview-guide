from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, File, Form, Request, UploadFile
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from interview_guide.common.api.responses import result_response
from interview_guide.common.db.models import (
    KnowledgeBase,
    KnowledgeBaseQuestion,
    RagChatMessage,
    RagSessionKnowledgeBase,
    VectorStore,
)
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.redis.streams import KB_VECTORIZE
from interview_guide.common.result import Result
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

router = APIRouter(prefix="/api/knowledgebase")


async def session_dependency(
    request: Request,
) -> AsyncIterator[AsyncSession]:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    async with infrastructure.database.sessions() as session:
        yield session


Session = Annotated[AsyncSession, Depends(session_dependency)]


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


async def list_query(
    session: AsyncSession,
    *,
    vector_status: str | None = None,
    category: str | None = None,
    uncategorized: bool = False,
    keyword: str | None = None,
) -> list[KnowledgeBase]:
    statement = select(KnowledgeBase)
    if vector_status is not None:
        statement = statement.where(KnowledgeBase.vector_status == vector_status)
    if uncategorized:
        statement = statement.where(KnowledgeBase.category.is_(None))
    elif category is not None:
        statement = statement.where(KnowledgeBase.category == category)
    if keyword:
        value = f"%{keyword.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(KnowledgeBase.name).like(value),
                func.lower(KnowledgeBase.original_filename).like(value),
                func.lower(KnowledgeBase.category).like(value),
            )
        )
    result = await session.scalars(statement.order_by(KnowledgeBase.uploaded_at.desc()))
    return list(result)


@router.get("/list")
async def list_knowledge_bases(
    session: Session,
    sortBy: str | None = None,
    vectorStatus: str | None = None,
) -> Response:
    status = vectorStatus.upper() if vectorStatus and vectorStatus.strip() else None
    if status not in {None, "PENDING", "PROCESSING", "COMPLETED", "FAILED"}:
        return result_response(Result.error(500, f"无效的向量化状态: {vectorStatus}"))
    entities = await list_query(session, vector_status=status)
    if sortBy and sortBy.lower() in {"size", "access", "question"}:
        field = {
            "size": lambda value: value.file_size or 0,
            "access": lambda value: value.access_count or 0,
            "question": lambda value: value.question_count or 0,
        }[sortBy.lower()]
        entities.sort(key=field, reverse=True)
    return result_response(Result.ok([item(entity) for entity in entities]))


@router.post("/upload")
async def upload_knowledge_base(
    request: Request,
    session: Session,
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form()] = None,
    category: Annotated[str | None, Form()] = None,
) -> Response:
    data = await file.read()
    validate_file(data, KNOWLEDGE_BASE_MAX_BYTES, "知识库")
    detected = ContentTypeDetector().detect(
        data,
        file.filename,
        file.content_type,
    )
    validate_content_type(
        detected,
        file.filename,
        is_knowledge_base_mime_type,
        is_markdown_extension,
        f"不支持的文件类型: {detected}，支持的类型：PDF、DOCX、DOC、TXT、MD等",
    )
    file_hash = sha256_bytes(data)
    existing = await session.scalar(
        select(KnowledgeBase).where(KnowledgeBase.file_hash == file_hash)
    )
    if existing is not None:
        existing.access_count = (existing.access_count or 0) + 1
        await session.commit()
        return result_response(
            Result.ok(
                {
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
            )
        )
    await session.rollback()
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    content = await infrastructure.document_parser.parse(
        data,
        file.filename,
        detected,
    )
    if not content.strip():
        raise BusinessException(
            ErrorCode.INTERNAL_ERROR,
            "无法从文件中提取文本内容，请确保文件格式正确",
        )
    file_key = await infrastructure.storage.upload(
        data,
        file.filename,
        file.content_type,
        "knowledgebases",
    )
    file_url = infrastructure.storage.object_url(file_key)
    settings = request.app.state.settings
    uploaded_at = (
        datetime.fromisoformat(settings.migration_fixed_time)
        if settings.migration_fixed_time
        else datetime.now()
    )
    filename = file.filename or ""
    knowledge_name = (
        name.strip()
        if name and name.strip()
        else filename.rsplit(".", 1)[0]
        if "." in filename
        else filename or "未命名知识库"
    )
    async with session.begin():
        entity = KnowledgeBase(
            access_count=1,
            category=category.strip() if category and category.strip() else None,
            chunk_count=None,
            content_type=file.content_type,
            file_hash=file_hash,
            file_size=len(data),
            last_accessed_at=uploaded_at,
            name=knowledge_name,
            original_filename=filename,
            question_count=0,
            storage_key=file_key,
            storage_url=file_url,
            uploaded_at=uploaded_at,
            vector_error=None,
            vector_status="PENDING",
        )
        session.add(entity)
        await session.flush()
    try:
        await infrastructure.streams.add(
            KB_VECTORIZE.key,
            {
                "kbId": str(entity.id),
                "content": content,
                "retryCount": "0",
            },
        )
    except Exception as error:
        async with session.begin():
            stored = await session.get(KnowledgeBase, entity.id)
            if stored is not None:
                stored.vector_status = "FAILED"
                stored.vector_error = f"任务入队失败: {error}"[:500]
    return result_response(
        Result.ok(
            {
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
        )
    )


@router.get("/categories")
async def categories(session: Session) -> Response:
    result = await session.scalars(
        select(KnowledgeBase.category)
        .where(KnowledgeBase.category.is_not(None))
        .distinct()
        .order_by(KnowledgeBase.category)
    )
    return result_response(Result.ok(list(result)))


@router.get("/uncategorized")
async def uncategorized(session: Session) -> Response:
    return result_response(
        Result.ok([item(value) for value in await list_query(session, uncategorized=True)])
    )


@router.get("/search")
async def search(session: Session, keyword: str) -> Response:
    return result_response(
        Result.ok([item(value) for value in await list_query(session, keyword=keyword)])
    )


@router.get("/stats")
async def statistics(session: Session) -> Response:
    total = await session.scalar(select(func.count()).select_from(KnowledgeBase))
    user_messages = await session.scalar(
        select(func.count()).select_from(RagChatMessage).where(RagChatMessage.type == "USER")
    )
    access = await session.scalar(select(func.coalesce(func.sum(KnowledgeBase.access_count), 0)))
    completed = await session.scalar(
        select(func.count())
        .select_from(KnowledgeBase)
        .where(KnowledgeBase.vector_status == "COMPLETED")
    )
    processing = await session.scalar(
        select(func.count())
        .select_from(KnowledgeBase)
        .where(KnowledgeBase.vector_status == "PROCESSING")
    )
    return result_response(
        Result.ok(
            {
                "totalCount": total or 0,
                "totalQuestionCount": user_messages or 0,
                "totalAccessCount": access or 0,
                "completedCount": completed or 0,
                "processingCount": processing or 0,
            }
        )
    )


@router.put("/{knowledge_base_id}/category")
async def update_category(
    knowledge_base_id: int,
    session: Session,
    payload: Annotated[dict[str, str | None], Body()],
) -> Response:
    entity = await session.get(KnowledgeBase, knowledge_base_id)
    if entity is None:
        raise BusinessException(
            ErrorCode.KNOWLEDGE_BASE_NOT_FOUND,
            "知识库不存在",
        )
    category = payload.get("category")
    entity.category = category if category and category.strip() else None
    await session.commit()
    return result_response(Result.ok())


@router.get("/{knowledge_base_id}/download")
async def download_knowledge_base(
    knowledge_base_id: int,
    request: Request,
    session: Session,
) -> Response:
    entity = await session.get(KnowledgeBase, knowledge_base_id)
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
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    content = await infrastructure.storage.download(entity.storage_key)
    return Response(
        content=content,
        headers=original_file_download_headers(
            entity.original_filename,
            entity.content_type,
        ),
    )


@router.delete("/{knowledge_base_id}")
async def delete_knowledge_base(
    knowledge_base_id: int,
    request: Request,
    session: Session,
) -> Response:
    entity = await session.get(KnowledgeBase, knowledge_base_id)
    if entity is None:
        raise BusinessException(ErrorCode.NOT_FOUND, "知识库不存在")
    storage_key = entity.storage_key
    await session.rollback()
    async with session.begin():
        await session.execute(
            delete(RagSessionKnowledgeBase).where(
                RagSessionKnowledgeBase.knowledge_base_id == knowledge_base_id
            )
        )
        await session.execute(
            delete(KnowledgeBaseQuestion).where(
                KnowledgeBaseQuestion.knowledge_base_id == knowledge_base_id
            )
        )
        await session.execute(delete(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id))
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    async with infrastructure.database.sessions() as vector_session, vector_session.begin():
        await vector_session.execute(
            delete(VectorStore).where(
                VectorStore.metadata_json["kb_id"].astext == str(knowledge_base_id)
            )
        )
    with suppress(Exception):
        await infrastructure.storage.delete(storage_key)
    return result_response(Result.ok())


@router.get("/{knowledge_base_id}")
async def get_knowledge_base(
    knowledge_base_id: int,
    session: Session,
) -> Response:
    entity = await session.get(KnowledgeBase, knowledge_base_id)
    if entity is None:
        return result_response(Result.error(500, "知识库不存在"))
    return result_response(Result.ok(item(entity)))
