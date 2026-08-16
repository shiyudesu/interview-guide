from __future__ import annotations

from interview_guide.common.ai.skills import Skill, SkillRepository
from interview_guide.modules.interview_skill.models import (
    DisplayResponse,
    SkillCategoryResponse,
    SkillResponse,
)


class InterviewSkillService:
    def __init__(self, repository: SkillRepository) -> None:
        self._repository = repository

    def all(self) -> list[SkillResponse]:
        return [self._response(skill) for skill in self._repository.all()]

    def get(self, skill_id: str) -> SkillResponse:
        return self._response(self._repository.get(skill_id))

    @staticmethod
    def _response(skill: Skill) -> SkillResponse:
        return SkillResponse(
            id=skill.skill_id,
            name=skill.display_name,
            description=skill.description,
            categories=[
                SkillCategoryResponse(
                    key=category.key,
                    label=category.label,
                    priority=category.priority,
                    ref=category.ref,
                    shared=category.shared,
                )
                for category in skill.categories
            ],
            is_preset=True,
            source_jd=None,
            persona=skill.persona,
            display=(
                DisplayResponse(
                    icon=skill.display.icon,
                    gradient=skill.display.gradient,
                    icon_bg=skill.display.icon_bg,
                    icon_color=skill.display.icon_color,
                )
                if skill.display is not None
                else None
            ),
        )
