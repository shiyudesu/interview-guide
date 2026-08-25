from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from starlette.responses import Response

from interview_guide.common.ai.prompts import PromptRepository
from interview_guide.common.ai.skills import SkillRepository
from interview_guide.common.ai.structured import StructuredOutputInvoker
from interview_guide.common.api.responses import STANDARD_ERROR_RESPONSES, result_response
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import LEGACY_OWNER_ID
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.metrics import ApplicationMetrics
from interview_guide.common.redis.rate_limit import (
    RateLimitDimension,
    RateLimitRule,
)
from interview_guide.common.result import Result
from interview_guide.modules.auth.dependencies import current_actor
from interview_guide.modules.interview.cache import InterviewSessionCache
from interview_guide.modules.interview.models import (
    CreateInterviewRequest,
    CurrentQuestionResponse,
    InterviewDetailDTO,
    InterviewReportDTO,
    InterviewSessionDTO,
    SessionListItemDTO,
    SubmitTurnRequest,
    SubmitTurnResponse,
)
from interview_guide.modules.interview.question import (
    InterviewQuestionService,
    InterviewSkillLibrary,
)
from interview_guide.modules.interview.repository import InterviewRepository
from interview_guide.modules.interview.service import InterviewService
from interview_guide.modules.interview.turn import InterviewTurnDecisionService
from interview_guide.modules.knowledge_base.api import client_ip

router = APIRouter(
    prefix="/api/interview/sessions",
    responses=STANDARD_ERROR_RESPONSES,
)
RESOURCES = Path(__file__).resolve().parents[4] / "resources"
PROMPTS = PromptRepository(RESOURCES)
SKILL_REPOSITORY = SkillRepository(RESOURCES)
SKILLS = InterviewSkillLibrary(SKILL_REPOSITORY, RESOURCES)


def build_interview_service(
    infrastructure: RuntimeInfrastructure,
    settings: Settings,
    metrics: ApplicationMetrics | None = None,
    user_id: uuid.UUID | None = None,
) -> InterviewService:
    registry = infrastructure.provider_resolver.for_user(user_id or LEGACY_OWNER_ID)
    repository = InterviewRepository(
        infrastructure.database.sessions,
        now=datetime.now,
        user_id=user_id,
    )
    structured = StructuredOutputInvoker(infrastructure.llm_adapter)
    questions = InterviewQuestionService(
        registry,
        structured,
        PROMPTS,
        infrastructure.prompt_sanitizer,
        SKILLS,
    )
    decisions = InterviewTurnDecisionService(
        StructuredOutputInvoker(infrastructure.llm_adapter, max_attempts=1),
        PROMPTS,
        infrastructure.prompt_sanitizer,
        SKILLS,
        settings,
    )
    return InterviewService(
        repository,
        InterviewSessionCache(infrastructure.redis.client, user_id),
        infrastructure.streams,
        questions,
        decisions,
        registry,
        infrastructure.blocking_executor,
        follow_up_count=settings.interview_follow_up_count,
        turn_lease_seconds=settings.interview_turn_lease_seconds,
        turn_wait_seconds=settings.interview_turn_decision_timeout_seconds + 5,
        metrics=metrics,
        uuid_factory=uuid.uuid4,
    )


async def interview_service(request: Request) -> AsyncIterator[InterviewService]:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    actor = current_actor(request)
    yield build_interview_service(
        infrastructure,
        request.app.state.settings,
        request.app.state.metrics,
        actor.user_id,
    )


ServiceDependency = Annotated[InterviewService, Depends(interview_service)]


async def enforce_rate_limit(
    request: Request,
    scope: str,
    rules: tuple[RateLimitRule, ...],
) -> None:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    actor = current_actor(request)
    await infrastructure.rate_limiter.check(
        scope=scope,
        rules=rules,
        client_ip=client_ip(request),
        user_id=str(actor.user_id),
        now_ms=time.time_ns() // 1_000_000,
    )


@router.get("", response_model=list[SessionListItemDTO])
async def list_sessions(
    service: ServiceDependency,
    sessionIds: Annotated[list[str] | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Response:
    return result_response(
        Result.ok(
            await service.list_sessions(
                session_ids=sessionIds,
                limit=limit,
                offset=offset,
            )
        )
    )


@router.post("", response_model=InterviewSessionDTO, status_code=201)
async def create_session(
    request: Request,
    payload: CreateInterviewRequest,
    service: ServiceDependency,
) -> Response:
    await enforce_rate_limit(
        request,
        "interview:create",
        (
            RateLimitRule(RateLimitDimension.GLOBAL, 5),
            RateLimitRule(RateLimitDimension.IP, 5),
            RateLimitRule(RateLimitDimension.USER, 5),
        ),
    )
    return result_response(
        Result.ok(await service.create_session(payload)),
        status_code=201,
    )


@router.get("/unfinished/{resume_id}", response_model=InterviewSessionDTO)
async def unfinished_session(
    resume_id: int,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.find_unfinished_or_throw(resume_id)))


@router.get("/{session_id}", response_model=InterviewSessionDTO)
async def get_session(
    session_id: str,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.get_session(session_id)))


@router.get("/{session_id}/question", response_model=CurrentQuestionResponse)
async def current_question(
    session_id: str,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.current_question(session_id)))


@router.post("/{session_id}/turns", response_model=SubmitTurnResponse)
async def submit_turn(
    request: Request,
    session_id: str,
    payload: SubmitTurnRequest,
    service: ServiceDependency,
) -> Response:
    await enforce_rate_limit(
        request,
        "interview:submit-turn",
        (
            RateLimitRule(RateLimitDimension.GLOBAL, 10),
            RateLimitRule(RateLimitDimension.USER, 10),
        ),
    )
    return result_response(Result.ok(await service.submit_turn(session_id, payload)))


@router.post("/{session_id}/complete", status_code=204)
async def complete_interview(
    session_id: str,
    service: ServiceDependency,
) -> Response:
    await service.complete(session_id)
    return result_response(Result.ok())


@router.get("/{session_id}/report", response_model=InterviewReportDTO)
async def report(
    session_id: str,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.report(session_id)))


@router.post("/{session_id}/report", status_code=204)
async def regenerate_report(
    session_id: str,
    service: ServiceDependency,
) -> Response:
    await service.regenerate_report(session_id)
    return result_response(Result.ok())


@router.get("/{session_id}/details", response_model=InterviewDetailDTO)
async def detail(
    session_id: str,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.detail(session_id)))


@router.get(
    "/{session_id}/export",
    responses={200: {"content": {"application/pdf": {}}}},
)
async def export_pdf(
    session_id: str,
    service: ServiceDependency,
) -> Response:
    content, headers = await service.export_pdf(session_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers=headers,
    )


@router.delete("/{session_id}", status_code=204)
async def delete_interview(
    session_id: str,
    service: ServiceDependency,
) -> Response:
    await service.delete(session_id)
    return result_response(Result.ok())
