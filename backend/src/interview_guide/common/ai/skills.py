from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from interview_guide.common.errors import BusinessException, ErrorCode

FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
SKILLS_TOOL_DESCRIPTION = (
    "Execute a skill within the main conversation\n\n"
    "<skills_instructions>\n"
    "When users ask you to perform tasks, check if any of the available skills below "
    "can help complete the task more effectively. Skills provide specialized "
    "capabilities and domain knowledge.\n\n"
    "How to use skills:\n"
    "- Invoke skills using this tool with the skill name only (no arguments)\n"
    '- When you invoke a skill, you will see <command-message>The "{{name}}" skill '
    "is loading</command-message>\n"
    "- The skill's prompt will expand and provide detailed instructions on how to "
    "complete the task\n\n"
    "NOTE: Response always starts start with the base directory of the skill execution "
    "environment. You can use this to retrieve additional files of call shell "
    "commands.\n"
    "Skill description follows after the base directory line.\n\n"
    "Important:\n"
    "- Only use skills listed in <available_skills> below\n"
    "- Do not invoke a skill that is already running\n"
    "</skills_instructions>\n\n"
    "<available_skills>\n"
    "{skills}\n"
    "</available_skills>\n"
)


@dataclass(frozen=True)
class SkillDisplay:
    icon: str | None
    gradient: str | None
    icon_bg: str | None
    icon_color: str | None


@dataclass(frozen=True)
class SkillCategory:
    key: str
    label: str
    priority: str
    ref: str | None
    shared: bool


@dataclass(frozen=True)
class Skill:
    skill_id: str
    name: str
    display_name: str
    description: str | None
    persona: str
    display: SkillDisplay | None
    categories: tuple[SkillCategory, ...]


class SkillRepository:
    def __init__(self, resources_dir: Path) -> None:
        self._skills_dir = resources_dir / "skills"
        self._skills = self._load()

    def all(self) -> tuple[Skill, ...]:
        return tuple(self._skills[key] for key in sorted(self._skills))

    def get(self, skill_id: str) -> Skill:
        try:
            return self._skills[skill_id]
        except KeyError as error:
            raise BusinessException(
                ErrorCode.BAD_REQUEST,
                f"未找到面试主题: {skill_id}",
            ) from error

    def reference(self, skill_id: str, category_key: str) -> str | None:
        skill = self.get(skill_id)
        category = next(
            (candidate for candidate in skill.categories if candidate.key == category_key),
            None,
        )
        if category is None or category.ref is None:
            return None
        if category.shared:
            path = self._skills_dir / "_shared/references" / category.ref
        else:
            path = self._skills_dir / skill_id / category.ref
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def tool_definition(self) -> dict[str, Any]:
        skills = "\n".join(
            (
                "<skill>\n"
                f"  <name>{skill.name}</name>\n"
                f"  <description>{skill.description}</description>\n"
                "</skill>"
            )
            for skill in self.all()
        )
        return {
            "type": "function",
            "function": {
                "name": "Skill",
                "description": SKILLS_TOOL_DESCRIPTION.format(skills=skills),
                "parameters": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "additionalProperties": False,
                    "properties": {
                        "command": {
                            "description": ('The skill name (no arguments). E.g., "pdf" or "xlsx"'),
                            "type": "string",
                        }
                    },
                    "required": ["command"],
                    "strict": True,
                    "type": "object",
                },
            },
        }

    def _load(self) -> dict[str, Skill]:
        skills: dict[str, Skill] = {}
        for skill_path in sorted(self._skills_dir.glob("*/SKILL.md")):
            skill_id = skill_path.parent.name
            if skill_id == "_shared":
                continue
            markdown = skill_path.read_text(encoding="utf-8")
            match = FRONT_MATTER.fullmatch(markdown)
            if match is None:
                raise BusinessException(
                    ErrorCode.BAD_REQUEST,
                    f"Skill 文件格式错误（缺少 front matter）: {skill_path}",
                )
            front_matter = self._mapping(yaml.safe_load(match.group(1)))
            metadata_path = skill_path.parent / "skill.meta.yml"
            metadata = self._mapping(yaml.safe_load(metadata_path.read_text(encoding="utf-8")))
            name = str(front_matter.get("name") or "")
            if not name:
                continue
            display_data = self._mapping(metadata.get("display"))
            display = (
                SkillDisplay(
                    icon=self._optional_string(display_data.get("icon")),
                    gradient=self._optional_string(display_data.get("gradient")),
                    icon_bg=self._optional_string(display_data.get("iconBg")),
                    icon_color=self._optional_string(display_data.get("iconColor")),
                )
                if display_data
                else None
            )
            categories = tuple(
                self._category(item) for item in self._sequence(metadata.get("categories"))
            )
            skills[skill_id] = Skill(
                skill_id=skill_id,
                name=name,
                display_name=str(metadata.get("displayName") or name),
                description=self._optional_string(front_matter.get("description")),
                persona=match.group(2).strip(),
                display=display,
                categories=categories,
            )
        return skills

    @classmethod
    def _category(cls, raw: Any) -> SkillCategory:
        value = cls._mapping(raw)
        return SkillCategory(
            key=str(value["key"]),
            label=str(value["label"]),
            priority=str(value["priority"]),
            ref=cls._optional_string(value.get("ref")),
            shared=bool(value.get("shared", False)),
        )

    @staticmethod
    def _mapping(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _sequence(value: Any) -> list[Any]:
        return list(value) if isinstance(value, list) else []

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        return str(value) if value is not None else None
