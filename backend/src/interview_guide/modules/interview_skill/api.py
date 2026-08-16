from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from starlette.responses import Response

from interview_guide.common.ai.skills import SkillRepository
from interview_guide.common.api.responses import result_response
from interview_guide.common.result import Result
from interview_guide.modules.interview_skill.service import InterviewSkillService

router = APIRouter(prefix="/api/interview/skills")
RESOURCES = Path(__file__).resolve().parents[4] / "resources"
service = InterviewSkillService(SkillRepository(RESOURCES))


@router.get("")
async def list_skills() -> Response:
    return result_response(Result.ok(service.all()))


@router.get("/{skill_id}")
async def get_skill(skill_id: str) -> Response:
    return result_response(Result.ok(service.get(skill_id)))
