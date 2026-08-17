from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Request
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
from interview_guide.modules.interview.question import (
    InterviewSkillLibrary,
    JdParseService,
)
from interview_guide.modules.interview_skill.models import ParseJdRequest
from interview_guide.modules.interview_skill.service import InterviewSkillService
from interview_guide.modules.knowledge_base.api import client_ip

router = APIRouter(prefix="/api/interview/skills")
RESOURCES = Path(__file__).resolve().parents[4] / "resources"
service = InterviewSkillService(SkillRepository(RESOURCES))
skill_repository = SkillRepository(RESOURCES)
skill_library = InterviewSkillLibrary(skill_repository, RESOURCES)
prompts = PromptRepository(RESOURCES)


@router.get("")
async def list_skills() -> Response:
    return result_response(Result.ok(service.all()))


@router.get("/{skill_id}")
async def get_skill(skill_id: str) -> Response:
    return result_response(Result.ok(service.get(skill_id)))


@router.post("/parse-jd")
async def parse_jd(request: Request, payload: ParseJdRequest) -> Response:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    await infrastructure.rate_limiter.check(
        class_name="InterviewSkillController",
        method_name="parseJd",
        rules=(RateLimitRule(RateLimitDimension.IP, 5),),
        client_ip=client_ip(request),
        now_ms=time.time_ns() // 1_000_000,
    )
    parser = JdParseService(
        infrastructure.provider_registry,
        StructuredOutputInvoker(infrastructure.llm_adapter),
        prompts,
        infrastructure.prompt_sanitizer,
        skill_library,
    )
    return result_response(Result.ok(await parser.parse(payload.jd_text)))
