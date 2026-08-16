from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, Form, Request, UploadFile
from starlette.responses import Response

from interview_guide.common.api.responses import result_response
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.result import Result
from interview_guide.modules.knowledge_base.service import KnowledgeBaseService

router = APIRouter(prefix="/api/knowledgebase")


async def knowledge_base_service(
    request: Request,
) -> AsyncIterator[KnowledgeBaseService]:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    settings = request.app.state.settings
    fixed_now = (
        datetime.fromisoformat(settings.migration_fixed_time)
        if settings.migration_fixed_time
        else None
    )
    async with infrastructure.database.sessions() as session:
        yield KnowledgeBaseService(
            session,
            infrastructure.database.sessions,
            infrastructure.storage,
            infrastructure.streams,
            infrastructure.document_parser,
            now=(lambda: fixed_now) if fixed_now is not None else datetime.now,
        )


ServiceDependency = Annotated[
    KnowledgeBaseService,
    Depends(knowledge_base_service),
]


@router.get("/list")
async def list_knowledge_bases(
    service: ServiceDependency,
    sortBy: str | None = None,
    vectorStatus: str | None = None,
) -> Response:
    status = vectorStatus.upper() if vectorStatus and vectorStatus.strip() else None
    if status not in {None, "PENDING", "PROCESSING", "COMPLETED", "FAILED"}:
        return result_response(Result.error(500, f"无效的向量化状态: {vectorStatus}"))
    return result_response(Result.ok(await service.list_items(status, sortBy)))


@router.post("/upload")
async def upload_knowledge_base(
    service: ServiceDependency,
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form()] = None,
    category: Annotated[str | None, Form()] = None,
) -> Response:
    result = await service.upload(
        await file.read(),
        file.filename,
        file.content_type,
        name,
        category,
    )
    return result_response(Result.ok(result))


@router.get("/categories")
async def categories(service: ServiceDependency) -> Response:
    return result_response(Result.ok(await service.categories()))


@router.get("/category/{category}")
async def by_category(
    category: str,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.list_by_category(category)))


@router.get("/uncategorized")
async def uncategorized(service: ServiceDependency) -> Response:
    return result_response(Result.ok(await service.list_by_category(None)))


@router.get("/search")
async def search(
    keyword: str,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.search(keyword)))


@router.get("/stats")
async def statistics(service: ServiceDependency) -> Response:
    return result_response(Result.ok(await service.statistics()))


@router.put("/{knowledge_base_id}/category")
async def update_category(
    knowledge_base_id: int,
    service: ServiceDependency,
    payload: Annotated[dict[str, str | None], Body()],
) -> Response:
    await service.update_category(knowledge_base_id, payload.get("category"))
    return result_response(Result.ok())


@router.get("/{knowledge_base_id}/download")
async def download_knowledge_base(
    knowledge_base_id: int,
    service: ServiceDependency,
) -> Response:
    content, headers = await service.download(knowledge_base_id)
    return Response(content=content, headers=headers)


@router.post("/{knowledge_base_id}/revectorize")
async def revectorize_knowledge_base(
    knowledge_base_id: int,
    service: ServiceDependency,
) -> Response:
    await service.revectorize(knowledge_base_id)
    return result_response(Result.ok())


@router.delete("/{knowledge_base_id}")
async def delete_knowledge_base(
    knowledge_base_id: int,
    service: ServiceDependency,
) -> Response:
    await service.delete(knowledge_base_id)
    return result_response(Result.ok())


@router.get("/{knowledge_base_id}")
async def get_knowledge_base(
    knowledge_base_id: int,
    service: ServiceDependency,
) -> Response:
    entity = await service.detail(knowledge_base_id)
    if entity is None:
        return result_response(Result.error(500, "知识库不存在"))
    return result_response(Result.ok(entity))
