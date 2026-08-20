from __future__ import annotations

import time
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, Form, Request, UploadFile
from starlette.responses import Response, StreamingResponse

from interview_guide.common.ai.prompts import PromptRepository
from interview_guide.common.ai.skills import SkillRepository
from interview_guide.common.api.responses import result_response
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.redis.rate_limit import (
    RateLimitDimension,
    RateLimitRule,
)
from interview_guide.common.result import Result
from interview_guide.modules.knowledge_base.models import QueryRequest
from interview_guide.modules.knowledge_base.query_service import (
    KnowledgeBaseQueryService,
    QueryConfiguration,
)
from interview_guide.modules.knowledge_base.repository import (
    KnowledgeBaseQueryRepository,
)
from interview_guide.modules.knowledge_base.service import KnowledgeBaseService

router = APIRouter(prefix="/api/knowledgebase")
RESOURCES = Path(__file__).resolve().parents[4] / "resources"
QUERY_TOOLS = [SkillRepository(RESOURCES).tool_definition()]


async def knowledge_base_service(
    request: Request,
) -> AsyncIterator[KnowledgeBaseService]:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    async with infrastructure.database.sessions() as session:
        yield KnowledgeBaseService(
            session,
            infrastructure.database.sessions,
            infrastructure.storage,
            infrastructure.streams,
            infrastructure.document_parser,
            now=datetime.now,
        )


ServiceDependency = Annotated[
    KnowledgeBaseService,
    Depends(knowledge_base_service),
]


def knowledge_base_query_service(
    request: Request,
) -> KnowledgeBaseQueryService:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    return KnowledgeBaseQueryService(
        KnowledgeBaseQueryRepository(infrastructure.database.sessions),
        infrastructure.provider_registry,
        infrastructure.llm_adapter,
        PromptRepository(RESOURCES),
        QueryConfiguration.from_settings(request.app.state.settings),
        QUERY_TOOLS,
    )


QueryServiceDependency = Annotated[
    KnowledgeBaseQueryService,
    Depends(knowledge_base_query_service),
]


def client_ip(request: Request) -> str:
    for header in (
        "x-forwarded-for",
        "x-real-ip",
        "proxy-client-ip",
        "wl-proxy-client-ip",
    ):
        value = request.headers.get(header)
        if value and value.lower() != "unknown":
            return value.split(",", 1)[0].strip()
    return request.client.host if request.client is not None else "unknown"


async def enforce_query_rate_limit(
    request: Request,
    scope: str,
    count: int,
) -> None:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    await infrastructure.rate_limiter.check(
        scope=scope,
        rules=(
            RateLimitRule(RateLimitDimension.GLOBAL, float(count)),
            RateLimitRule(RateLimitDimension.IP, float(count)),
        ),
        client_ip=client_ip(request),
        now_ms=time.time_ns() // 1_000_000,
    )


def sse_data(content: str) -> bytes:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return ("".join(f"data:{line}\n" for line in normalized.split("\n")) + "\n").encode()


async def sse_stream(chunks: AsyncIterator[str]) -> AsyncIterator[bytes]:
    async for chunk in chunks:
        yield sse_data(chunk)


@router.get("/list")
async def list_knowledge_bases(
    service: ServiceDependency,
    sortBy: str | None = None,
    vectorStatus: str | None = None,
) -> Response:
    status = vectorStatus.upper() if vectorStatus and vectorStatus.strip() else None
    if status not in {None, "PENDING", "PROCESSING", "COMPLETED", "FAILED"}:
        raise BusinessException(
            ErrorCode.BAD_REQUEST,
            f"无效的向量化状态: {vectorStatus}",
        )
    return result_response(Result.ok(await service.list_items(status, sortBy)))


@router.post("/query")
async def query_knowledge_base(
    request: Request,
    payload: QueryRequest,
    service: QueryServiceDependency,
) -> Response:
    await enforce_query_rate_limit(request, "knowledge-base:query", 10)
    response = await service.query(payload)
    return result_response(Result.ok(response))


@router.post("/query/stream")
async def query_knowledge_base_stream(
    request: Request,
    payload: QueryRequest,
    service: QueryServiceDependency,
) -> Response:
    await enforce_query_rate_limit(request, "knowledge-base:query-stream", 5)
    chunks = await service.answer_question_stream(
        payload.knowledge_base_ids,
        payload.question,
    )
    return StreamingResponse(
        sse_stream(chunks),
        media_type="text/event-stream",
        headers={"Content-Type": "text/event-stream"},
    )


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
    return result_response(Result.ok(result), status_code=201)


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
        raise BusinessException(ErrorCode.KNOWLEDGE_BASE_NOT_FOUND)
    return result_response(Result.ok(entity))
