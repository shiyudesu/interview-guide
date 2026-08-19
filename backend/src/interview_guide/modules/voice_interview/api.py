from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Request
from starlette.responses import Response

from interview_guide.common.api.responses import result_response
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.result import Result
from interview_guide.modules.voice_interview.models import (
    CreateVoiceSessionRequest,
    VoiceAnswerDetail,
    VoiceEvaluationDetail,
    VoiceEvaluationStatusResponse,
)
from interview_guide.modules.voice_interview.repository import VoiceInterviewRepository
from interview_guide.modules.voice_interview.service import (
    VoiceEvaluationProducer,
    VoiceInterviewService,
)

router = APIRouter(prefix="/api/voice-interview")


def build_service(
    infrastructure: RuntimeInfrastructure,
) -> VoiceInterviewService:
    repository = VoiceInterviewRepository(
        infrastructure.database.sessions,
        datetime.now,
    )
    producer = VoiceEvaluationProducer(
        infrastructure.streams,
        repository,
        infrastructure.redis.client,
    )
    return VoiceInterviewService(
        repository,
        infrastructure.redis.client,
        producer,
        datetime.now,
    )


async def service_dependency(request: Request) -> VoiceInterviewService:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    return build_service(infrastructure)


Service = Annotated[VoiceInterviewService, Depends(service_dependency)]


@router.post("/sessions")
async def create_session(
    payload: CreateVoiceSessionRequest,
    service: Service,
) -> Response:
    return result_response(Result.ok(await service.create_session(payload)))


@router.get("/sessions/{session_id}")
async def get_session(session_id: int, service: Service) -> Response:
    session = await service.get_session_response(session_id)
    if session is None:
        return result_response(Result.error(500, f"Session not found: {session_id}"))
    return result_response(Result.ok(session))


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: int, service: Service) -> Response:
    await service.end_session(session_id)
    return result_response(Result.ok())


@router.put("/sessions/{session_id}/pause")
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


@router.put("/sessions/{session_id}/resume")
async def resume_session(session_id: int, service: Service) -> Response:
    return result_response(Result.ok(await service.resume_session(session_id)))


@router.get("/sessions")
async def list_sessions(
    service: Service,
    userId: str | None = None,
    status: str | None = None,
) -> Response:
    return result_response(Result.ok(await service.list_sessions(userId, status)))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int, service: Service) -> Response:
    await service.delete_session(session_id)
    return result_response(Result.ok())


@router.get("/sessions/{session_id}/messages")
async def messages(session_id: int, service: Service) -> Response:
    return result_response(Result.ok(await service.messages(session_id)))


def evaluation_detail(entity: Any) -> VoiceEvaluationDetail:
    raw_answers = json.loads(entity.question_evaluations_json or "[]")
    raw_references = json.loads(entity.reference_answers_json or "[]")
    references: dict[int, dict[str, Any]] = {}
    for index, reference in enumerate(raw_references):
        references.setdefault(
            int(reference.get("questionIndex", index)),
            reference,
        )
    return VoiceEvaluationDetail(
        session_id=entity.session_id,
        total_questions=len(raw_answers),
        overall_score=entity.overall_score,
        overall_feedback=entity.overall_feedback,
        strengths=json.loads(entity.strengths_json or "[]"),
        improvements=json.loads(entity.improvements_json or "[]"),
        answers=[
            VoiceAnswerDetail(
                question_index=int(answer.get("questionIndex", index)),
                question=str(answer.get("question", "")),
                category=answer.get("category"),
                user_answer=answer.get("userAnswer"),
                score=int(answer.get("score", 0)),
                feedback=answer.get("feedback"),
                reference_answer=references.get(
                    int(answer.get("questionIndex", index)),
                    {},
                ).get("referenceAnswer"),
                key_points=references.get(
                    int(answer.get("questionIndex", index)),
                    {},
                ).get("keyPoints"),
            )
            for index, answer in enumerate(raw_answers)
        ],
    )


@router.get("/sessions/{session_id}/evaluation")
async def get_evaluation(session_id: int, service: Service) -> Response:
    session = await service.get_session(session_id)
    if session is None:
        from interview_guide.common.errors import BusinessException, ErrorCode

        raise BusinessException(
            ErrorCode.VOICE_SESSION_NOT_FOUND,
            f"会话不存在: {session_id}",
        )
    evaluation = None
    if session.evaluate_status == "COMPLETED":
        entity = await service.repository.evaluation(session_id)
        if entity is not None:
            evaluation = evaluation_detail(entity)
    return result_response(
        Result.ok(
            VoiceEvaluationStatusResponse(
                evaluate_status=session.evaluate_status,
                evaluate_error=session.evaluate_error,
                evaluate_status_updated_at=session.updated_at,
                evaluation=evaluation,
            )
        )
    )


@router.post("/sessions/{session_id}/evaluation")
async def generate_evaluation(session_id: int, service: Service) -> Response:
    session = await service.get_session(session_id)
    if session is None:
        from interview_guide.common.errors import BusinessException, ErrorCode

        raise BusinessException(
            ErrorCode.VOICE_SESSION_NOT_FOUND,
            f"会话不存在: {session_id}",
        )
    if session.evaluate_status == "COMPLETED":
        entity = await service.repository.evaluation(session_id)
        return result_response(
            Result.ok(
                VoiceEvaluationStatusResponse(
                    evaluate_status="COMPLETED",
                    evaluate_status_updated_at=session.updated_at,
                    evaluation=(evaluation_detail(entity) if entity is not None else None),
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
