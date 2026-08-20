from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from starlette.responses import Response

from interview_guide.common.api.responses import result_response
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.redis.rate_limit import RateLimitDimension, RateLimitRule
from interview_guide.common.result import Result
from interview_guide.modules.interview.api import (
    ServiceDependency as InterviewServiceDependency,
)
from interview_guide.modules.knowledge_base.api import client_ip
from interview_guide.modules.knowledge_base.question_models import (
    CreateKnowledgeBaseInterviewRequest,
    CreateKnowledgeBaseQuestionRequest,
    GenerateKnowledgeBaseQuestionsRequest,
    KnowledgeBaseQuestionStatus,
    UpdateKnowledgeBaseQuestionRequest,
    UpdateKnowledgeBaseQuestionStatusRequest,
)
from interview_guide.modules.knowledge_base.question_service import (
    KnowledgeBaseInterviewService,
    KnowledgeBaseQuestionService,
    QuestionGenerationStateService,
    QuestionGenStreamProducer,
)

router = APIRouter()


def generation_state(
    request: Request,
) -> QuestionGenerationStateService:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    return QuestionGenerationStateService(infrastructure.database.sessions)


async def question_service(
    request: Request,
) -> AsyncIterator[KnowledgeBaseQuestionService]:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    state = generation_state(request)
    async with infrastructure.database.sessions() as session:
        yield KnowledgeBaseQuestionService(
            session,
            state,
            QuestionGenStreamProducer(infrastructure.streams, state),
        )


QuestionServiceDependency = Annotated[
    KnowledgeBaseQuestionService,
    Depends(question_service),
]


async def enforce_generation_rate_limit(request: Request) -> None:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    await infrastructure.rate_limiter.check(
        scope="knowledge-base:generate-questions",
        rules=(
            RateLimitRule(RateLimitDimension.GLOBAL, 2),
            RateLimitRule(RateLimitDimension.IP, 2),
        ),
        client_ip=client_ip(request),
        now_ms=time.time_ns() // 1_000_000,
    )


@router.get("/api/knowledgebase/{knowledge_base_id}/questions")
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


@router.get("/api/knowledgebase/{knowledge_base_id}/questions/categories")
async def list_question_categories(
    knowledge_base_id: int,
    service: QuestionServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.list_categories(knowledge_base_id)))


@router.post("/api/knowledgebase/{knowledge_base_id}/questions/generate")
async def generate_questions(
    knowledge_base_id: int,
    payload: GenerateKnowledgeBaseQuestionsRequest,
    request: Request,
    service: QuestionServiceDependency,
) -> Response:
    await enforce_generation_rate_limit(request)
    return result_response(
        Result.ok(
            await service.submit_generation_task(
                knowledge_base_id,
                payload,
            )
        )
    )


@router.get("/api/knowledgebase/{knowledge_base_id}/questions/generation-status")
async def question_generation_status(
    knowledge_base_id: int,
    service: QuestionServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.generation_status(knowledge_base_id)))


@router.post("/api/knowledgebase/{knowledge_base_id}/questions")
async def create_question(
    knowledge_base_id: int,
    payload: CreateKnowledgeBaseQuestionRequest,
    service: QuestionServiceDependency,
) -> Response:
    return result_response(
        Result.ok(await service.create_question(knowledge_base_id, payload)),
        status_code=201,
    )


@router.put("/api/knowledgebase/questions/{question_id}")
async def update_question(
    question_id: int,
    payload: UpdateKnowledgeBaseQuestionRequest,
    service: QuestionServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.update_question(question_id, payload)))


@router.put("/api/knowledgebase/questions/{question_id}/status")
async def update_question_status(
    question_id: int,
    payload: UpdateKnowledgeBaseQuestionStatusRequest,
    service: QuestionServiceDependency,
) -> Response:
    assert payload.status is not None
    return result_response(Result.ok(await service.update_status(question_id, payload.status)))


@router.delete("/api/knowledgebase/questions/{question_id}")
async def delete_question(
    question_id: int,
    service: QuestionServiceDependency,
) -> Response:
    await service.delete_question(question_id)
    return result_response(Result.ok())


@router.post("/api/knowledgebase-interviews/sessions")
async def create_knowledge_base_interview(
    payload: CreateKnowledgeBaseInterviewRequest,
    request: Request,
    interview: InterviewServiceDependency,
) -> Response:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    service = KnowledgeBaseInterviewService(
        infrastructure.database.sessions,
        interview,
    )
    return result_response(
        Result.ok(await service.create_session(payload)),
        status_code=201,
    )


@router.get("/api/knowledgebase/{knowledge_base_id}/interview-capacity")
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
    service = KnowledgeBaseInterviewService(
        infrastructure.database.sessions,
        interview,
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
