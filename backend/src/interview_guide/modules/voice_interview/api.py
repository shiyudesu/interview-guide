from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request
from starlette.responses import Response

from interview_guide.common.api.responses import STANDARD_ERROR_RESPONSES, result_response
from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.metrics import ApplicationMetrics
from interview_guide.common.result import Result
from interview_guide.modules.interview.api import build_interview_service
from interview_guide.modules.voice_interview.models import (
    CreateVoiceSessionRequest,
    VoiceEvaluationStatusResponse,
    VoiceInterviewMessageResponse,
    VoiceSessionMeta,
    VoiceSessionResponse,
)
from interview_guide.modules.voice_interview.repository import VoiceInterviewRepository
from interview_guide.modules.voice_interview.service import VoiceInterviewService

router = APIRouter(prefix="/api/voice-interview", responses=STANDARD_ERROR_RESPONSES)


def build_service(
    infrastructure: RuntimeInfrastructure,
    settings: Settings,
    metrics: ApplicationMetrics | None = None,
) -> VoiceInterviewService:
    repository = VoiceInterviewRepository(
        infrastructure.database.sessions,
        datetime.now,
    )
    return VoiceInterviewService(
        repository,
        infrastructure.redis.client,
        build_interview_service(infrastructure, settings, metrics),
        datetime.now,
    )


async def service_dependency(request: Request) -> VoiceInterviewService:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    return build_service(
        infrastructure,
        request.app.state.settings,
        request.app.state.metrics,
    )


Service = Annotated[VoiceInterviewService, Depends(service_dependency)]


@router.post("/sessions", response_model=VoiceSessionResponse, status_code=201)
async def create_session(
    payload: CreateVoiceSessionRequest,
    service: Service,
) -> Response:
    return result_response(
        Result.ok(await service.create_session(payload)),
        status_code=201,
    )


@router.get("/sessions/{session_id}", response_model=VoiceSessionResponse)
async def get_session(session_id: int, service: Service) -> Response:
    session = await service.get_session_response(session_id)
    if session is None:
        raise BusinessException(
            ErrorCode.VOICE_SESSION_NOT_FOUND,
            f"Session not found: {session_id}",
        )
    return result_response(Result.ok(session))


@router.post("/sessions/{session_id}/end", status_code=204)
async def end_session(session_id: int, service: Service) -> Response:
    await service.end_session(session_id)
    return result_response(Result.ok())


@router.put("/sessions/{session_id}/pause", status_code=204)
async def pause_session(
    session_id: int,
    service: Service,
    payload: Annotated[dict[str, str], Body()],
) -> Response:
    await service.pause_session(
        session_id,
        payload.get("reason", "user_initiated"),
    )
    return result_response(Result.ok())


@router.put("/sessions/{session_id}/resume", response_model=VoiceSessionResponse)
async def resume_session(session_id: int, service: Service) -> Response:
    return result_response(Result.ok(await service.resume_session(session_id)))


@router.get("/sessions", response_model=list[VoiceSessionMeta])
async def list_sessions(
    service: Service,
    userId: str | None = None,
    status: str | None = None,
    sessionIds: Annotated[list[int] | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Response:
    return result_response(
        Result.ok(
            await service.list_sessions(
                userId,
                status,
                session_ids=sessionIds,
                limit=limit,
                offset=offset,
            )
        )
    )


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: int, service: Service) -> Response:
    await service.delete_session(session_id)
    return result_response(Result.ok())


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[VoiceInterviewMessageResponse],
)
async def messages(session_id: int, service: Service) -> Response:
    return result_response(Result.ok(await service.messages(session_id)))


@router.get(
    "/sessions/{session_id}/evaluation",
    response_model=VoiceEvaluationStatusResponse,
)
async def get_evaluation(session_id: int, service: Service) -> Response:
    session = await service.get_session(session_id)
    if session is None:
        from interview_guide.common.errors import BusinessException, ErrorCode

        raise BusinessException(
            ErrorCode.VOICE_SESSION_NOT_FOUND,
            f"会话不存在: {session_id}",
        )
    evaluation = await service.evaluation_report(session_id)
    status = "COMPLETED" if evaluation is not None else session.evaluate_status
    return result_response(
        Result.ok(
            VoiceEvaluationStatusResponse(
                evaluate_status=status,
                evaluate_error=session.evaluate_error,
                evaluate_status_updated_at=session.updated_at,
                evaluation=evaluation,
            )
        )
    )


@router.post(
    "/sessions/{session_id}/evaluation",
    response_model=VoiceEvaluationStatusResponse,
)
async def generate_evaluation(session_id: int, service: Service) -> Response:
    session = await service.get_session(session_id)
    if session is None:
        from interview_guide.common.errors import BusinessException, ErrorCode

        raise BusinessException(
            ErrorCode.VOICE_SESSION_NOT_FOUND,
            f"会话不存在: {session_id}",
        )
    evaluation = await service.evaluation_report(session_id)
    if evaluation is not None:
        return result_response(
            Result.ok(
                VoiceEvaluationStatusResponse(
                    evaluate_status="COMPLETED",
                    evaluate_status_updated_at=session.updated_at,
                    evaluation=evaluation,
                )
            )
        )
    if session.evaluate_status == "PROCESSING":
        return result_response(
            Result.ok(
                VoiceEvaluationStatusResponse(
                    evaluate_status="PROCESSING",
                    evaluate_status_updated_at=session.updated_at,
                )
            )
        )
    await service.trigger_evaluation(session_id)
    return result_response(
        Result.ok(
            VoiceEvaluationStatusResponse(
                evaluate_status="PENDING",
                evaluate_status_updated_at=service._now(),
            )
        )
    )
