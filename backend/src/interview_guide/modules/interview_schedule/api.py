from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from interview_guide.common.api.responses import result_response
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.result import Result
from interview_guide.modules.interview_schedule.models import (
    CreateInterviewRequest,
    ParseRequest,
)
from interview_guide.modules.interview_schedule.parser import InterviewParseService
from interview_guide.modules.interview_schedule.service import (
    InterviewScheduleService,
    schedule_now,
)

router = APIRouter(prefix="/api/interview-schedule")


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    async with infrastructure.database.sessions() as session:
        yield session


SessionDependency = Annotated[AsyncSession, Depends(database_session)]


async def schedule_service(
    request: Request,
    session: SessionDependency,
) -> InterviewScheduleService:
    settings = request.app.state.settings
    return InterviewScheduleService(
        session,
        now=lambda: schedule_now(settings),
    )


ServiceDependency = Annotated[
    InterviewScheduleService,
    Depends(schedule_service),
]


async def parse_service(request: Request) -> InterviewParseService:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    settings = request.app.state.settings
    return InterviewParseService(
        infrastructure.provider_registry,
        infrastructure.llm_adapter,
        infrastructure.prompt_sanitizer,
        schedule_now(settings),
    )


ParseServiceDependency = Annotated[
    InterviewParseService,
    Depends(parse_service),
]


def parse_query_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(
            f"Failed to convert value of type 'java.lang.String' "
            f"to required type 'java.time.LocalDateTime'; {value}"
        ) from error
    if parsed.tzinfo is not None:
        raise ValueError(
            f"Failed to convert value of type 'java.lang.String' "
            f"to required type 'java.time.LocalDateTime'; {value}"
        )
    return parsed


@router.post("")
async def create_schedule(
    payload: CreateInterviewRequest,
    service: ServiceDependency,
) -> Response:
    created = await service.create(payload)
    return result_response(Result.ok(created))


@router.post("/parse")
async def parse_schedule(
    payload: ParseRequest,
    service: ParseServiceDependency,
) -> Response:
    parsed = await service.parse(payload.raw_text, payload.source)
    return result_response(Result.ok(parsed))


@router.get("/{schedule_id}")
async def get_schedule(
    schedule_id: int,
    service: ServiceDependency,
) -> Response:
    schedule = await service.get(schedule_id)
    return result_response(Result.ok(schedule))


@router.get("")
async def list_schedules(
    service: ServiceDependency,
    status: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> Response:
    schedules = await service.list(
        status,
        parse_query_datetime(start),
        parse_query_datetime(end),
    )
    return result_response(Result.ok(schedules))


@router.put("/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    payload: CreateInterviewRequest,
    service: ServiceDependency,
) -> Response:
    updated = await service.update(
        schedule_id,
        payload,
    )
    return result_response(Result.ok(updated))


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    service: ServiceDependency,
) -> Response:
    await service.delete(schedule_id)
    return result_response(Result.ok())


async def update_schedule_status(
    schedule_id: int,
    status: Annotated[str, Query()],
    service: ServiceDependency,
) -> Response:
    updated = await service.update_status(
        schedule_id,
        status,
    )
    return result_response(Result.ok(updated))


@router.patch("/{schedule_id}/status")
async def patch_schedule_status(
    schedule_id: int,
    status: Annotated[str, Query()],
    service: ServiceDependency,
) -> Response:
    return await update_schedule_status(schedule_id, status, service)


@router.put("/{schedule_id}/status")
async def put_schedule_status(
    schedule_id: int,
    status: Annotated[str, Query()],
    service: ServiceDependency,
) -> Response:
    return await update_schedule_status(schedule_id, status, service)
