from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from interview_guide.common.api.responses import STANDARD_ERROR_RESPONSES, result_response
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.result import Result
from interview_guide.modules.auth.dependencies import current_actor
from interview_guide.modules.interview_schedule.models import (
    CreateInterviewRequest,
    InterviewScheduleResponse,
    ParseRequest,
    ParseResponse,
)
from interview_guide.modules.interview_schedule.parser import InterviewParseService
from interview_guide.modules.interview_schedule.service import (
    InterviewScheduleService,
    schedule_now,
)

router = APIRouter(
    prefix="/api/interview-schedule",
    responses=STANDARD_ERROR_RESPONSES,
)


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    async with infrastructure.database.sessions() as session:
        yield session


SessionDependency = Annotated[AsyncSession, Depends(database_session)]


async def schedule_service(
    session: SessionDependency,
    request: Request,
) -> InterviewScheduleService:
    actor = current_actor(request)
    return InterviewScheduleService(
        session,
        now=schedule_now,
        user_id=actor.user_id,
    )


ServiceDependency = Annotated[
    InterviewScheduleService,
    Depends(schedule_service),
]


async def parse_service(request: Request) -> InterviewParseService:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    actor = current_actor(request)
    return InterviewParseService(
        infrastructure.provider_resolver.for_user(actor.user_id),
        infrastructure.llm_adapter,
        infrastructure.prompt_sanitizer,
        schedule_now(),
    )


ParseServiceDependency = Annotated[
    InterviewParseService,
    Depends(parse_service),
]


def parse_query_datetime(
    value: str | None,
    parameter: str,
) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{parameter} 时间格式错误，请使用不带时区的 ISO-8601 本地时间") from error
    if parsed.tzinfo is not None:
        raise ValueError(f"{parameter} 时间格式错误，请使用不带时区的 ISO-8601 本地时间")
    return parsed


@router.post("", response_model=InterviewScheduleResponse, status_code=201)
async def create_schedule(
    payload: CreateInterviewRequest,
    service: ServiceDependency,
) -> Response:
    created = await service.create(payload)
    return result_response(Result.ok(created), status_code=201)


@router.post("/parse", response_model=ParseResponse)
async def parse_schedule(
    payload: ParseRequest,
    service: ParseServiceDependency,
) -> Response:
    parsed = await service.parse(payload.raw_text, payload.source)
    return result_response(Result.ok(parsed))


@router.get("/{schedule_id}", response_model=InterviewScheduleResponse)
async def get_schedule(
    schedule_id: int,
    service: ServiceDependency,
) -> Response:
    schedule = await service.get(schedule_id)
    return result_response(Result.ok(schedule))


@router.get("", response_model=list[InterviewScheduleResponse])
async def list_schedules(
    service: ServiceDependency,
    status: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> Response:
    schedules = await service.list(
        status,
        parse_query_datetime(start, "start"),
        parse_query_datetime(end, "end"),
    )
    return result_response(Result.ok(schedules))


@router.put("/{schedule_id}", response_model=InterviewScheduleResponse)
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


@router.delete("/{schedule_id}", status_code=204)
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


@router.patch("/{schedule_id}/status", response_model=InterviewScheduleResponse)
async def patch_schedule_status(
    schedule_id: int,
    status: Annotated[str, Query()],
    service: ServiceDependency,
) -> Response:
    return await update_schedule_status(schedule_id, status, service)


@router.put("/{schedule_id}/status", response_model=InterviewScheduleResponse)
async def put_schedule_status(
    schedule_id: int,
    status: Annotated[str, Query()],
    service: ServiceDependency,
) -> Response:
    return await update_schedule_status(schedule_id, status, service)
