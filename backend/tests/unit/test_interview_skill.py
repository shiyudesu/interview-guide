from __future__ import annotations

from pathlib import Path

from interview_guide.common.ai.skills import SkillRepository
from interview_guide.modules.interview_skill.service import InterviewSkillService

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_skill_response_order_and_content_matches_java_contract() -> None:
    service = InterviewSkillService(SkillRepository(BACKEND_ROOT / "resources"))

    skills = service.all()
    first = skills[0]

    assert [skill.id for skill in skills] == [
        "ai-agent-dev",
        "algorithm",
        "ali-backend",
        "bytedance-backend",
        "frontend",
        "java-backend",
        "java-backend-tencent",
        "python-backend",
        "system-design",
        "test-development",
    ]
    assert list(first.model_dump(by_alias=True)) == [
        "id",
        "name",
        "description",
        "categories",
        "isPreset",
        "sourceJd",
        "persona",
        "display",
    ]
    assert first.categories[0].key == "AGENT_BASIS"
