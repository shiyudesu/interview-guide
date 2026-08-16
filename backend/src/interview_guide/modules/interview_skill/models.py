from __future__ import annotations

from interview_guide.common.api.models import CamelModel


class DisplayResponse(CamelModel):
    icon: str | None
    gradient: str | None
    icon_bg: str | None
    icon_color: str | None


class SkillCategoryResponse(CamelModel):
    key: str
    label: str
    priority: str
    ref: str | None
    shared: bool


class SkillResponse(CamelModel):
    id: str
    name: str
    description: str | None
    categories: list[SkillCategoryResponse]
    is_preset: bool
    source_jd: str | None
    persona: str | None
    display: DisplayResponse | None
