from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from starlette.responses import Response

from interview_guide.common.api.responses import result_response
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.result import Result
from interview_guide.modules.resume.service import ResumeService

router = APIRouter(prefix="/api/resumes")


async def resume_service(request: Request) -> AsyncIterator[ResumeService]:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    async with infrastructure.database.sessions() as session:
        yield ResumeService(session, infrastructure.storage)


ServiceDependency = Annotated[ResumeService, Depends(resume_service)]


@router.get("")
async def list_resumes(service: ServiceDependency) -> Response:
    return result_response(Result.ok(await service.list()))


@router.get("/health")
async def resume_health() -> Response:
    return result_response(
        Result.ok(
            {
                "status": "UP",
                "service": "AI Interview Platform - Resume Service",
            }
        )
    )


@router.get("/{resume_id}/detail")
async def resume_detail(
    resume_id: int,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.detail(resume_id)))


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: int,
    service: ServiceDependency,
) -> Response:
    await service.delete(resume_id)
    return result_response(Result.ok())
