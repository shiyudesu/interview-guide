from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile
from starlette.responses import Response

from interview_guide.common.api.responses import result_response
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.result import Result
from interview_guide.modules.resume.service import ResumeService

router = APIRouter(prefix="/api/resumes")


async def resume_service(request: Request) -> AsyncIterator[ResumeService]:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    async with infrastructure.database.sessions() as session:
        yield ResumeService(
            session,
            infrastructure.storage,
            infrastructure.streams,
            infrastructure.document_parser,
        )


ServiceDependency = Annotated[ResumeService, Depends(resume_service)]


@router.get("")
async def list_resumes(service: ServiceDependency) -> Response:
    return result_response(Result.ok(await service.list()))


@router.post("/upload")
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


@router.get("/{resume_id}/detail")
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
    try:
        pdf, headers = await service.export_pdf(resume_id)
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers=headers,
        )
    except Exception:
        return Response(status_code=500)


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: int,
    service: ServiceDependency,
) -> Response:
    await service.delete(resume_id)
    return result_response(Result.ok())


@router.post("/{resume_id}/reanalyze")
async def reanalyze_resume(
    resume_id: int,
    service: ServiceDependency,
) -> Response:
    await service.reanalyze(resume_id)
    return result_response(Result.ok())
