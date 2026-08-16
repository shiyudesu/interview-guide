from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from interview_guide.common.api.responses import result_response
from interview_guide.common.db.models import KnowledgeBase, RagChatMessage
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.result import Result

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


@router.get("/{knowledge_base_id}")
async def get_knowledge_base(
    knowledge_base_id: int,
    session: Session,
) -> Response:
    entity = await session.get(KnowledgeBase, knowledge_base_id)
    if entity is None:
        return result_response(Result.error(500, "知识库不存在"))
    return result_response(Result.ok(item(entity)))
