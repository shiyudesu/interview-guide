from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from starlette.responses import Response

from interview_guide.common.api.responses import STANDARD_ERROR_RESPONSES, result_response
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.redis.rate_limit import RateLimitDimension, RateLimitRule
from interview_guide.common.result import Result
from interview_guide.modules.auth.dependencies import current_actor
from interview_guide.modules.interview.api import (
    ServiceDependency as InterviewServiceDependency,
)
from interview_guide.modules.interview.models import InterviewSessionDTO
from interview_guide.modules.knowledge_base.api import client_ip
from interview_guide.modules.knowledge_base.question_models import (
    CategoryCount,
    CreateKnowledgeBaseInterviewRequest,
    CreateKnowledgeBaseQuestionRequest,
    GenerateKnowledgeBaseQuestionsRequest,
    KnowledgeBaseInterviewCapacityResponse,
    KnowledgeBaseQuestionDTO,
    KnowledgeBaseQuestionStatus,
    QuestionGenStatusResponse,
    UpdateKnowledgeBaseQuestionRequest,
    UpdateKnowledgeBaseQuestionStatusRequest,
)
from interview_guide.modules.knowledge_base.question_service import (
    KnowledgeBaseInterviewService,
    KnowledgeBaseQuestionService,
    QuestionGenerationStateService,
    QuestionGenStreamProducer,
)

router = APIRouter(responses=STANDARD_ERROR_RESPONSES)


def generation_state(
    request: Request,
) -> QuestionGenerationStateService:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    actor = current_actor(request)
    return QuestionGenerationStateService(
        infrastructure.database.sessions,
        user_id=actor.user_id,
    )


async def question_service(
    request: Request,
) -> AsyncIterator[KnowledgeBaseQuestionService]:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    actor = current_actor(request)
    registry = infrastructure.provider_resolver.for_user(actor.user_id)
    state = generation_state(request)
    async with infrastructure.database.sessions() as session:
        yield KnowledgeBaseQuestionService(
            session,
            state,
            QuestionGenStreamProducer(infrastructure.streams, state),
            user_id=actor.user_id,
            default_provider_alias=await registry.default_chat_alias(),
        )


QuestionServiceDependency = Annotated[
    KnowledgeBaseQuestionService,
    Depends(question_service),
]


async def enforce_generation_rate_limit(request: Request) -> None:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    actor = current_actor(request)
    await infrastructure.rate_limiter.check(
        scope="knowledge-base:generate-questions",
        rules=(
            RateLimitRule(RateLimitDimension.GLOBAL, 2),
            RateLimitRule(RateLimitDimension.IP, 2),
            RateLimitRule(RateLimitDimension.USER, 2),
        ),
        client_ip=client_ip(request),
        user_id=str(actor.user_id),
        now_ms=time.time_ns() // 1_000_000,
    )


@router.get(
    "/api/knowledgebase/{knowledge_base_id}/questions",
    response_model=list[KnowledgeBaseQuestionDTO],
)
async def list_questions(
    knowledge_base_id: int,
    service: QuestionServiceDependency,
    status: KnowledgeBaseQuestionStatus | None = None,
    category: str | None = None,
    difficulty: str | None = None,
    keyword: str | None = None,
) -> Response:
    return result_response(
        Result.ok(
            await service.list_questions(
                knowledge_base_id,
                status,
                category,
                difficulty,
                keyword,
            )
        )
    )


@router.get(
    "/api/knowledgebase/{knowledge_base_id}/questions/categories",
    response_model=list[CategoryCount],
)
async def list_question_categories(
    knowledge_base_id: int,
    service: QuestionServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.list_categories(knowledge_base_id)))


@router.post(
    "/api/knowledgebase/{knowledge_base_id}/questions/generate",
    response_model=QuestionGenStatusResponse,
)
async def generate_questions(
    knowledge_base_id: int,
    payload: GenerateKnowledgeBaseQuestionsRequest,
    request: Request,
    service: QuestionServiceDependency,
) -> Response:
    await enforce_generation_rate_limit(request)
    effective_payload = (
        payload.model_copy(update={"follow_up_count": 0})
        if request.app.state.settings.competition_mode
        else payload
    )
    return result_response(
        Result.ok(
            await service.submit_generation_task(
                knowledge_base_id,
                effective_payload,
            )
        )
    )


@router.get(
    "/api/knowledgebase/{knowledge_base_id}/questions/generation-status",
    response_model=QuestionGenStatusResponse,
)
async def question_generation_status(
    knowledge_base_id: int,
    service: QuestionServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.generation_status(knowledge_base_id)))


@router.post(
    "/api/knowledgebase/{knowledge_base_id}/questions",
    response_model=KnowledgeBaseQuestionDTO,
    status_code=201,
)
async def create_question(
    knowledge_base_id: int,
    payload: CreateKnowledgeBaseQuestionRequest,
    service: QuestionServiceDependency,
) -> Response:
    return result_response(
        Result.ok(await service.create_question(knowledge_base_id, payload)),
        status_code=201,
    )


@router.put(
    "/api/knowledgebase/questions/{question_id}",
    response_model=KnowledgeBaseQuestionDTO,
)
async def update_question(
    question_id: int,
    payload: UpdateKnowledgeBaseQuestionRequest,
    service: QuestionServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.update_question(question_id, payload)))


@router.put(
    "/api/knowledgebase/questions/{question_id}/status",
    response_model=KnowledgeBaseQuestionDTO,
)
async def update_question_status(
    question_id: int,
    payload: UpdateKnowledgeBaseQuestionStatusRequest,
    service: QuestionServiceDependency,
) -> Response:
    assert payload.status is not None
    return result_response(Result.ok(await service.update_status(question_id, payload.status)))


@router.delete("/api/knowledgebase/questions/{question_id}", status_code=204)
async def delete_question(
    question_id: int,
    service: QuestionServiceDependency,
) -> Response:
    await service.delete_question(question_id)
    return result_response(Result.ok())


@router.post(
    "/api/knowledgebase-interviews/sessions",
    response_model=InterviewSessionDTO,
    status_code=201,
)
async def create_knowledge_base_interview(
    payload: CreateKnowledgeBaseInterviewRequest,
    request: Request,
    interview: InterviewServiceDependency,
) -> Response:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    actor = current_actor(request)
    service = KnowledgeBaseInterviewService(
        infrastructure.database.sessions,
        interview,
        user_id=actor.user_id,
    )
    return result_response(
        Result.ok(await service.create_session(payload)),
        status_code=201,
    )


@router.get(
    "/api/knowledgebase/{knowledge_base_id}/interview-capacity",
    response_model=KnowledgeBaseInterviewCapacityResponse,
)
async def knowledge_base_interview_capacity(
    knowledge_base_id: int,
    request: Request,
    interview: InterviewServiceDependency,
    category: str | None = None,
    difficulty: str = "mid",
    main_question_count: Annotated[
        int,
        Query(alias="mainQuestionCount"),
    ] = 5,
) -> Response:
    if main_question_count < 1 or main_question_count > 20:
        raise BusinessException(
            ErrorCode.INTERNAL_ERROR,
            "系统繁忙，请稍后重试",
        )
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    actor = current_actor(request)
    service = KnowledgeBaseInterviewService(
        infrastructure.database.sessions,
        interview,
        user_id=actor.user_id,
    )
    return result_response(
        Result.ok(
            await service.capacity(
                knowledge_base_id,
                category,
                difficulty,
                main_question_count,
            )
        )
    )
