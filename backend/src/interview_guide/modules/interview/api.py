from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from starlette.responses import Response

from interview_guide.common.ai.prompts import PromptRepository
from interview_guide.common.ai.skills import SkillRepository
from interview_guide.common.ai.structured import StructuredOutputInvoker
from interview_guide.common.api.responses import result_response
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.redis.rate_limit import (
    RateLimitDimension,
    RateLimitRule,
)
from interview_guide.common.result import Result
from interview_guide.modules.interview.cache import InterviewSessionCache
from interview_guide.modules.interview.evaluation import (
    AnswerEvaluationService,
    UnifiedEvaluationService,
)
from interview_guide.modules.interview.models import CreateInterviewRequest
from interview_guide.modules.interview.question import (
    InterviewQuestionService,
    InterviewSkillLibrary,
)
from interview_guide.modules.interview.repository import InterviewRepository
from interview_guide.modules.interview.service import InterviewService
from interview_guide.modules.knowledge_base.api import client_ip

router = APIRouter(prefix="/api/interview/sessions")
RESOURCES = Path(__file__).resolve().parents[4] / "resources"
PROMPTS = PromptRepository(RESOURCES)
SKILL_REPOSITORY = SkillRepository(RESOURCES)
SKILLS = InterviewSkillLibrary(SKILL_REPOSITORY, RESOURCES)
logger = logging.getLogger(__name__)


async def interview_service(request: Request) -> AsyncIterator[InterviewService]:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    settings = request.app.state.settings
    repository = InterviewRepository(
        infrastructure.database.sessions,
        now=datetime.now,
    )
    structured = StructuredOutputInvoker(infrastructure.llm_adapter)
    questions = InterviewQuestionService(
        infrastructure.provider_registry,
        structured,
        PROMPTS,
        infrastructure.prompt_sanitizer,
        SKILLS,
        follow_up_count=settings.interview_follow_up_count,
    )
    evaluation = AnswerEvaluationService(
        UnifiedEvaluationService(
            structured,
            PROMPTS,
            batch_size=settings.interview_evaluation_batch_size,
            tools=(SKILLS.tool_definition(),),
        ),
        SKILLS,
    )
    yield InterviewService(
        repository,
        InterviewSessionCache(infrastructure.redis.client),
        infrastructure.streams,
        questions,
        evaluation,
        infrastructure.provider_registry,
        infrastructure.blocking_executor,
        uuid_factory=uuid.uuid4,
    )


ServiceDependency = Annotated[InterviewService, Depends(interview_service)]


async def enforce_rate_limit(
    request: Request,
    method_name: str,
    rules: tuple[RateLimitRule, ...],
) -> None:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    await infrastructure.rate_limiter.check(
        class_name="InterviewController",
        method_name=method_name,
        rules=rules,
        client_ip=client_ip(request),
        now_ms=time.time_ns() // 1_000_000,
    )


@router.get("")
async def list_sessions(service: ServiceDependency) -> Response:
    return result_response(Result.ok(await service.list_sessions()))


@router.post("")
async def create_session(
    request: Request,
    payload: CreateInterviewRequest,
    service: ServiceDependency,
) -> Response:
    await enforce_rate_limit(
        request,
        "createSession",
        (
            RateLimitRule(RateLimitDimension.GLOBAL, 5),
            RateLimitRule(RateLimitDimension.IP, 5),
        ),
    )
    return result_response(Result.ok(await service.create_session(payload)))


@router.get("/unfinished/{resume_id}")
async def unfinished_session(
    resume_id: int,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.find_unfinished_or_throw(resume_id)))


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.get_session(session_id)))


@router.get("/{session_id}/question")
async def current_question(
    session_id: str,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.current_question(session_id)))


@router.post("/{session_id}/answers")
async def submit_answer(
    request: Request,
    session_id: str,
    body: dict[str, Any],
    service: ServiceDependency,
) -> Response:
    await enforce_rate_limit(
        request,
        "submitAnswer",
        (RateLimitRule(RateLimitDimension.GLOBAL, 10),),
    )
    question_index = body.get("questionIndex")
    answer = body.get("answer")
    if not isinstance(question_index, int) or isinstance(question_index, bool):
        raise TypeError("questionIndex must be Integer")
    if answer is not None and not isinstance(answer, str):
        raise TypeError("answer must be String")
    return result_response(
        Result.ok(
            await service.submit_answer(
                session_id,
                question_index,
                answer,
            )
        )
    )


@router.put("/{session_id}/answers")
async def save_answer(
    session_id: str,
    body: dict[str, Any],
    service: ServiceDependency,
) -> Response:
    question_index = body.get("questionIndex")
    answer = body.get("answer")
    if not isinstance(question_index, int) or isinstance(question_index, bool):
        raise TypeError("questionIndex must be Integer")
    if answer is not None and not isinstance(answer, str):
        raise TypeError("answer must be String")
    await service.save_answer(session_id, question_index, answer)
    return result_response(Result.ok())


@router.post("/{session_id}/complete")
async def complete_interview(
    session_id: str,
    service: ServiceDependency,
) -> Response:
    await service.complete(session_id)
    return result_response(Result.ok())


@router.get("/{session_id}/report")
async def report(
    session_id: str,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.generate_report(session_id)))


@router.get("/{session_id}/details")
async def detail(
    session_id: str,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.detail(session_id)))


@router.get("/{session_id}/export")
async def export_pdf(
    session_id: str,
    service: ServiceDependency,
) -> Response:
    try:
        content, headers = await service.export_pdf(session_id)
        return Response(
            content=content,
            media_type="application/pdf",
            headers=headers,
        )
    except Exception:
        logger.exception("failed to export interview PDF sessionId=%s", session_id)
        return Response(status_code=500)


@router.delete("/{session_id}")
async def delete_interview(
    session_id: str,
    service: ServiceDependency,
) -> Response:
    await service.delete(session_id)
    return result_response(Result.ok())
