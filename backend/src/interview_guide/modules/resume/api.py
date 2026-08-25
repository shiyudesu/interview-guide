from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from starlette.responses import Response

from interview_guide.common.api.responses import STANDARD_ERROR_RESPONSES, result_response
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.result import Result
from interview_guide.modules.auth.dependencies import current_actor
from interview_guide.modules.resume.models import (
    ResumeDetailResponse,
    ResumeListResponse,
    UploadResumeResponse,
)
from interview_guide.modules.resume.service import ResumeService

router = APIRouter(prefix="/api/resumes", responses=STANDARD_ERROR_RESPONSES)


async def resume_service(request: Request) -> AsyncIterator[ResumeService]:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    actor = current_actor(request)
    registry = infrastructure.provider_resolver.for_user(actor.user_id)
    async with infrastructure.database.sessions() as session:
        yield ResumeService(
            session,
            infrastructure.storage,
            infrastructure.streams,
            infrastructure.document_parser,
            infrastructure.blocking_executor,
            user_id=actor.user_id,
            analysis_provider_alias=await registry.default_chat_alias(),
        )


ServiceDependency = Annotated[ResumeService, Depends(resume_service)]


@router.get("", response_model=list[ResumeListResponse])
async def list_resumes(
    service: ServiceDependency,
    ids: Annotated[list[int] | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Response:
    return result_response(Result.ok(await service.list(ids=ids, limit=limit, offset=offset)))


@router.post("/upload", response_model=UploadResumeResponse, status_code=201)
async def upload_resume(
    file: Annotated[UploadFile, File()],
    service: ServiceDependency,
) -> Response:
    data = await file.read()
    result = await service.upload(
        data,
        file.filename,
        file.content_type,
    )
    return result_response(Result.ok(result), status_code=201)


@router.get("/health")
async def resume_health() -> Response:
    return result_response(
        Result.ok(
            {
                "status": "ok",
                "service": "resume",
            }
        )
    )


@router.get("/{resume_id}/detail", response_model=ResumeDetailResponse)
async def resume_detail(
    resume_id: int,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.detail(resume_id)))


@router.get("/{resume_id}/export")
async def export_resume_pdf(
    resume_id: int,
    service: ServiceDependency,
) -> Response:
    pdf, headers = await service.export_pdf(resume_id)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers=headers,
    )


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(
    resume_id: int,
    service: ServiceDependency,
) -> Response:
    await service.delete(resume_id)
    return result_response(Result.ok())


@router.post("/{resume_id}/reanalyze", status_code=204)
async def reanalyze_resume(
    resume_id: int,
    service: ServiceDependency,
) -> Response:
    await service.reanalyze(resume_id)
    return result_response(Result.ok())
