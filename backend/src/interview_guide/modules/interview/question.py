from __future__ import annotations

import asyncio
import logging
import math
import re
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.prompts import (
    DATA_BOUNDARY_INSTRUCTION,
    PromptRepository,
    PromptSanitizer,
)
from interview_guide.common.ai.providers import LlmProviderRegistry
from interview_guide.common.ai.skills import Skill, SkillRepository
from interview_guide.common.ai.structured import StructuredOutputInvoker, structured_output_format
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.modules.interview.models import (
    CategoryRequest,
    HistoricalQuestion,
    PlannedInterviewQuestion,
)

logger = logging.getLogger(__name__)
DEFAULT_SKILL_ID = "java-backend"
DEFAULT_DIFFICULTY = "mid"
DEFAULT_QUESTION_TYPE = "GENERAL"
CUSTOM_SKILL_ID = "custom"
RESUME_QUESTION_RATIO = 0.6
MAX_REFERENCE_SECTION_CHARS = 12_000
MAX_EVALUATION_REFERENCE_SECTION_CHARS = 6_000
MAX_SINGLE_REFERENCE_CHARS = 3_000
SAFE_REFERENCE = re.compile(r"^[a-zA-Z0-9._/-]+$")
GENERIC_MODE_SYSTEM_APPEND = """

# 通用面试模式
本次面试无候选人简历，请出该方向的标准面试题。
- 禁止出现"你在简历中提到..."、"你在项目中..."等暗示存在简历的表述
- 问题表述应与简历无关，直接考察该方向的技术能力
"""
DIFFICULTY_DESCRIPTIONS = {
    "junior": "校招/0-1年经验。考察基础概念和简单应用。",
    "mid": "1-3年经验。考察原理理解和实战经验。",
    "senior": "3年+经验。考察架构设计和深度调优。",
}
GENERIC_FALLBACK_QUESTIONS = (
    ("请描述一个你主导解决的技术难题，你的分析思路是什么？", "GENERAL", "综合能力"),
    ("你在做技术方案选型时，通常考虑哪些因素？请举例说明。", "GENERAL", "综合能力"),
    ("请分享一次你处理线上故障的经历，从发现到修复的完整过程。", "GENERAL", "综合能力"),
    ("你如何保证代码质量？介绍你实践过的有效手段。", "GENERAL", "综合能力"),
    ("描述一个你做过的技术优化案例，优化的动机、方案和效果。", "GENERAL", "综合能力"),
    ("你在团队协作中遇到过最大的分歧是什么？如何解决的？", "GENERAL", "综合能力"),
)


class QuestionOutput(BaseModel):
    question: str | None = None
    type: str | None = None
    category: str | None = None
    topicSummary: str | None = None


class QuestionListOutput(BaseModel):
    questions: list[QuestionOutput | None] | None = None


class JdCategoryOutput(BaseModel):
    key: str | None = None
    label: str | None = None
    priority: str | None = None
    ref: str | None = None
    shared: bool | None = None


class JdCategoryListOutput(BaseModel):
    categories: list[JdCategoryOutput] | None = None


@dataclass(frozen=True)
class ResolvedCategory:
    key: str
    label: str
    priority: str
    ref: str | None
    shared: bool
    source_skill_id: str | None


@dataclass(frozen=True)
class ResolvedSkill:
    skill_id: str
    name: str
    description: str | None
    categories: tuple[ResolvedCategory, ...]
    source_jd: str | None
    persona: str | None


@dataclass(frozen=True)
class GenerationInput:
    provider_id: str | None
    skill_id: str
    difficulty: str
    resume_text: str | None
    question_count: int
    historical_questions: list[HistoricalQuestion]
    custom_categories: list[CategoryRequest] | None
    jd_text: str | None


class QuestionGenerationState(TypedDict, total=False):
    generation_input: GenerationInput
    skill: ResolvedSkill
    difficulty_description: str
    historical_section: str
    resume_count: int
    direction_count: int
    resume_questions: list[PlannedInterviewQuestion]
    direction_questions: list[PlannedInterviewQuestion]
    questions: list[PlannedInterviewQuestion]


QUESTION_OUTPUT_FORMAT = structured_output_format(
    {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "question": {"type": "string"},
                        "topicSummary": {"type": "string"},
                        "type": {"type": "string"},
                    },
                    "required": [
                        "category",
                        "question",
                        "topicSummary",
                        "type",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["questions"],
        "additionalProperties": False,
    }
)
JD_OUTPUT_FORMAT = structured_output_format(
    {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "categories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "label": {"type": "string"},
                        "priority": {"type": "string"},
                        "ref": {"type": "string"},
                        "shared": {"type": "boolean"},
                    },
                    "required": ["key", "label", "priority", "ref", "shared"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["categories"],
        "additionalProperties": False,
    }
)


def stable_key_order(values: list[str | None]) -> list[str | None]:
    return sorted(set(values), key=lambda item: (item is not None, item or ""))


class InterviewSkillLibrary:
    def __init__(self, repository: SkillRepository, resources: Path) -> None:
        self._repository = repository
        self._skills_dir = resources / "skills"
        self._reference_index = self._build_reference_index()

    def resolve(
        self,
        skill_id: str,
        custom_categories: list[CategoryRequest] | None,
        jd_text: str | None,
    ) -> ResolvedSkill:
        if skill_id == CUSTOM_SKILL_ID and custom_categories:
            categories: list[ResolvedCategory] = []
            for category in custom_categories:
                if category.key is None or category.label is None:
                    continue
                key = self._sanitize_category_key(category.key)
                label = self._sanitize_category_label(category.label)
                mapped = self._reference_index.get(key)
                categories.append(
                    ResolvedCategory(
                        key=key,
                        label=label,
                        priority=category.priority or "NORMAL",
                        ref=mapped.ref if mapped is not None else category.ref,
                        shared=mapped.shared if mapped is not None else bool(category.shared),
                        source_skill_id=(mapped.source_skill_id if mapped is not None else None),
                    )
                )
            return ResolvedSkill(
                skill_id=CUSTOM_SKILL_ID,
                name="自定义面试（JD 解析）",
                description="基于职位描述提取的面试方向",
                categories=tuple(categories),
                source_jd=jd_text or "",
                persona=None,
            )
        return self._preset(self._repository.get(skill_id))

    def allocation(
        self,
        categories: tuple[ResolvedCategory, ...],
        total_questions: int,
    ) -> OrderedDict[str, int]:
        always = [item for item in categories if item.priority == "ALWAYS_ONE"]
        core = [item for item in categories if item.priority == "CORE"]
        normal = [item for item in categories if item.priority not in {"ALWAYS_ONE", "CORE"}]
        allocation: OrderedDict[str, int] = OrderedDict()
        remaining = total_questions
        for category in always:
            if remaining > 0:
                allocation[category.key] = 1
                remaining -= 1
        for group in (core, normal):
            for category in group:
                if remaining > 0:
                    allocation[category.key] = 1
                    remaining -= 1
        while remaining > 0:
            for group in (core, normal):
                for category in group:
                    if remaining <= 0:
                        break
                    allocation[category.key] = allocation.get(category.key, 0) + 1
                    remaining -= 1
            if not core and not normal:
                break
        for category in (*core, *normal):
            allocation.setdefault(category.key, 0)
        return allocation

    def allocation_description(
        self,
        allocation: OrderedDict[str, int],
        categories: tuple[ResolvedCategory, ...],
    ) -> str:
        return "".join(
            f"| {category.label} | {allocation.get(category.key, 0)} 题 | {category.priority} |\n"
            for category in categories
            if allocation.get(category.key, 0) > 0
        )

    def generation_reference_section(
        self,
        skill: ResolvedSkill,
        allocation: OrderedDict[str, int],
    ) -> str:
        return self._reference_section(
            skill,
            lambda item: allocation.get(item.key, 0) > 0,
            MAX_REFERENCE_SECTION_CHARS,
        )

    def evaluation_reference_section(self, skill_id: str | None) -> str:
        if skill_id is None or not skill_id.strip():
            return ""
        try:
            skill = self.resolve(skill_id, None, None)
            return self._reference_section(
                skill,
                lambda _: True,
                MAX_EVALUATION_REFERENCE_SECTION_CHARS,
            )
        except Exception:
            logger.warning(
                "failed to load evaluation reference; using empty reference",
                exc_info=True,
            )
            return ""

    def reference_file_list(self) -> str:
        rows: OrderedDict[str, str] = OrderedDict()
        for skill in self._repository.all():
            for category in skill.categories:
                if category.ref:
                    rows.setdefault(
                        category.ref,
                        f"| {category.ref} | "
                        f"{'shared' if category.shared else 'skill-local'} | "
                        f"{skill.display_name} | {category.label} |\n",
                    )
        if not rows:
            return "（无可用参考文件）"
        return (
            "| 文件名 | 范围 | 来源 Skill | 覆盖内容 |\n"
            "|--------|------|-------------|----------|\n" + "".join(rows.values())
        )

    def tool_definition(self) -> dict[str, object]:
        return cast(dict[str, object], self._repository.tool_definition())

    def _reference_section(
        self,
        skill: ResolvedSkill,
        include: Callable[[ResolvedCategory], bool],
        max_chars: int,
    ) -> str:
        sections: list[str] = []
        for category in skill.categories:
            if not include(category):
                continue
            if not category.ref:
                continue
            content = self._load_reference(skill, category)
            if not content:
                continue
            sections.append(f"### {category.label} ({category.key})\n{content}")
            joined = "\n\n".join(sections)
            if len(joined) >= max_chars:
                return joined[:max_chars] + "\n...（references 已截断）"
        return "\n\n".join(sections) if sections else "未配置 references。"

    def _load_reference(
        self,
        skill: ResolvedSkill,
        category: ResolvedCategory,
    ) -> str:
        reference = category.ref or ""
        if (
            ".." in reference
            or reference.startswith(("/", "\\"))
            or SAFE_REFERENCE.fullmatch(reference) is None
        ):
            return ""
        locations: list[Path] = []

        def add_skill(skill_id: str | None) -> None:
            if not skill_id or skill_id == CUSTOM_SKILL_ID:
                return
            locations.extend(
                (
                    self._skills_dir / skill_id / "references" / reference,
                    self._skills_dir / skill_id / reference,
                )
            )

        if category.shared:
            locations.append(self._skills_dir / "_shared/references" / reference)
        effective_skill_id = (
            category.source_skill_id
            if skill.skill_id == CUSTOM_SKILL_ID and not category.shared
            else skill.skill_id
        )
        add_skill(effective_skill_id)
        if not category.shared:
            locations.append(self._skills_dir / "_shared/references" / reference)
        if skill.skill_id == CUSTOM_SKILL_ID or category.shared:
            for preset in self._repository.all():
                add_skill(preset.skill_id)
        seen: set[Path] = set()
        for path in locations:
            if path in seen:
                continue
            seen.add(path)
            if path.is_file():
                content = path.read_text(encoding="utf-8").strip()
                if len(content) > MAX_SINGLE_REFERENCE_CHARS:
                    return content[:MAX_SINGLE_REFERENCE_CHARS] + "\n...（单文件内容已截断）"
                return content
        return ""

    def _preset(self, skill: Skill) -> ResolvedSkill:
        return ResolvedSkill(
            skill_id=skill.skill_id,
            name=skill.display_name,
            description=skill.description,
            categories=tuple(
                ResolvedCategory(
                    key=category.key,
                    label=category.label,
                    priority=category.priority,
                    ref=category.ref,
                    shared=category.shared,
                    source_skill_id=skill.skill_id,
                )
                for category in skill.categories
            ),
            source_jd=None,
            persona=skill.persona,
        )

    def _build_reference_index(self) -> dict[str, ResolvedCategory]:
        result: dict[str, ResolvedCategory] = {}
        for skill in self._repository.all():
            for category in skill.categories:
                if category.ref and category.key not in result:
                    result[category.key] = ResolvedCategory(
                        key=category.key,
                        label=category.label,
                        priority=category.priority,
                        ref=category.ref,
                        shared=category.shared,
                        source_skill_id=skill.skill_id,
                    )
        return result

    @staticmethod
    def _sanitize_category_key(value: str) -> str:
        trimmed = value.strip()[:50]
        upper = re.sub(r"[^A-Z0-9_]", "_", trimmed.upper())
        if not upper:
            return "UNKNOWN"
        return upper if upper[0].isalpha() else f"CAT_{upper}"

    @staticmethod
    def _sanitize_category_label(value: str) -> str:
        trimmed = re.sub(r"[\r\n]+", " ", value.strip())[:50]
        return trimmed or "未命名"


class InterviewQuestionService:
    def __init__(
        self,
        registry: LlmProviderRegistry,
        structured: StructuredOutputInvoker,
        prompts: PromptRepository,
        sanitizer: PromptSanitizer,
        skills: InterviewSkillLibrary,
    ) -> None:
        self._registry = registry
        self._structured = structured
        self._prompts = prompts
        self._sanitizer = sanitizer
        self._skills = skills
        graph = StateGraph(QuestionGenerationState)
        graph.add_node("resolve_skill", self._resolve_skill_node)
        graph.add_node("allocate_question_counts", self._allocate_node)
        graph.add_node("generate_with_fallback", self._generate_node)
        graph.add_node("merge_and_cap", self._merge_node)
        graph.add_edge(START, "resolve_skill")
        graph.add_edge("resolve_skill", "allocate_question_counts")
        graph.add_edge("allocate_question_counts", "generate_with_fallback")
        graph.add_edge("generate_with_fallback", "merge_and_cap")
        graph.add_edge("merge_and_cap", END)
        self._graph = graph.compile()

    async def generate(
        self,
        *,
        provider_id: str | None,
        skill_id: str,
        difficulty: str,
        resume_text: str | None,
        question_count: int,
        historical_questions: list[HistoricalQuestion],
        custom_categories: list[CategoryRequest] | None,
        jd_text: str | None,
    ) -> list[PlannedInterviewQuestion]:
        result = await self._graph.ainvoke(
            {
                "generation_input": GenerationInput(
                    provider_id=provider_id,
                    skill_id=skill_id,
                    difficulty=difficulty,
                    resume_text=resume_text,
                    question_count=question_count,
                    historical_questions=historical_questions,
                    custom_categories=custom_categories,
                    jd_text=jd_text,
                )
            }
        )
        questions = cast(list[PlannedInterviewQuestion], result["questions"])
        if len(questions) < question_count:
            fallback = self._fallback_questions(
                cast(ResolvedSkill, result["skill"]),
                question_count,
            )
            seen = {item.question for item in questions}
            questions.extend(item for item in fallback if item.question not in seen)
        return questions[:question_count]

    async def _resolve_skill_node(
        self,
        state: QuestionGenerationState,
    ) -> QuestionGenerationState:
        value = state["generation_input"]
        skill = self._skills.resolve(
            value.skill_id,
            value.custom_categories,
            value.jd_text,
        )
        return {
            "skill": skill,
            "difficulty_description": DIFFICULTY_DESCRIPTIONS.get(
                value.difficulty,
                DIFFICULTY_DESCRIPTIONS[DEFAULT_DIFFICULTY],
            ),
            "historical_section": self._historical_section(value.historical_questions),
        }

    async def _allocate_node(
        self,
        state: QuestionGenerationState,
    ) -> QuestionGenerationState:
        value = state["generation_input"]
        if value.resume_text is not None and value.resume_text.strip():
            resume_count = max(
                1,
                math.floor(value.question_count * RESUME_QUESTION_RATIO + 0.5),
            )
            return {
                "resume_count": resume_count,
                "direction_count": value.question_count - resume_count,
            }
        return {"resume_count": 0, "direction_count": value.question_count}

    async def _generate_node(
        self,
        state: QuestionGenerationState,
    ) -> QuestionGenerationState:
        value = state["generation_input"]
        skill = state["skill"]
        provider = await self._registry.get_chat(value.provider_id)
        if not value.resume_text or not value.resume_text.strip():
            questions = await self._generate_direction(
                provider,
                skill,
                state["difficulty_description"],
                state["direction_count"],
                state["historical_section"],
            )
            return {"questions": questions}
        resume_task = asyncio.create_task(
            self._generate_resume(
                provider,
                value.resume_text,
                state["resume_count"],
                skill,
                state["difficulty_description"],
                state["historical_section"],
            )
        )
        direction_task = asyncio.create_task(
            self._generate_direction(
                provider,
                skill,
                state["difficulty_description"],
                state["direction_count"],
                state["historical_section"],
            )
        )
        try:
            resume_questions = await resume_task
        except Exception:
            logger.exception("resume question generation failed; regenerating direction questions")
            direction_task.cancel()
            await asyncio.gather(direction_task, return_exceptions=True)
            return {
                "questions": await self._generate_direction(
                    provider,
                    skill,
                    state["difficulty_description"],
                    value.question_count,
                    state["historical_section"],
                )
            }
        try:
            direction_questions = await direction_task
        except Exception:
            logger.exception("direction question generation failed; returning resume questions")
            return {
                "questions": (
                    resume_questions
                    if resume_questions
                    else self._fallback_questions(skill, value.question_count)
                )
            }
        return {
            "resume_questions": resume_questions,
            "direction_questions": direction_questions,
        }

    async def _merge_node(
        self,
        state: QuestionGenerationState,
    ) -> QuestionGenerationState:
        if "questions" in state:
            return {"questions": state["questions"]}
        first = state.get("resume_questions", [])
        second = state.get("direction_questions", [])
        if not first and not second:
            return {
                "questions": self._fallback_questions(
                    state["skill"],
                    state["generation_input"].question_count,
                )
            }
        return {"questions": self._merge(first, second)}

    async def _generate_resume(
        self,
        provider: ProviderConfig,
        resume_text: str,
        question_count: int,
        skill: ResolvedSkill,
        difficulty_description: str,
        historical_section: str,
    ) -> list[PlannedInterviewQuestion]:
        system = (
            self._prompts.render("interview-question-resume-system.st")
            + self._persona_section(skill)
            + "\n\n"
            + QUESTION_OUTPUT_FORMAT
        )
        user = self._prompts.render(
            "interview-question-resume-user.st",
            {
                "questionCount": question_count,
                "skillName": skill.name,
                "skillDescription": skill.description or "",
                "difficultyDescription": difficulty_description,
                "resumeText": resume_text,
                "historicalSection": historical_section,
            },
        )
        result = await self._structured.invoke(
            provider,
            system,
            user,
            QuestionListOutput,
            ErrorCode.INTERVIEW_QUESTION_GENERATION_FAILED,
            "简历题生成失败：",
        )
        return self._cap(self._convert(result), question_count)

    async def _generate_direction(
        self,
        provider: ProviderConfig,
        skill: ResolvedSkill,
        difficulty_description: str,
        question_count: int,
        historical_section: str,
    ) -> list[PlannedInterviewQuestion]:
        allocation = self._skills.allocation(skill.categories, question_count)
        try:
            system = (
                self._prompts.render("interview-question-skill-system.st")
                + self._persona_section(skill)
                + GENERIC_MODE_SYSTEM_APPEND
                + QUESTION_OUTPUT_FORMAT
            )
            user = self._prompts.render(
                "interview-question-skill-user.st",
                {
                    "questionCount": question_count,
                    "difficultyDescription": difficulty_description,
                    "skillName": skill.name,
                    "skillDescription": skill.description or "",
                    "allocationTable": self._skills.allocation_description(
                        allocation,
                        skill.categories,
                    ),
                    "historicalSection": historical_section,
                    "referenceSection": self._skills.generation_reference_section(
                        skill,
                        allocation,
                    ),
                    "jdSection": self._jd_section(skill.source_jd),
                },
            )
            result = await self._structured.invoke(
                provider,
                system,
                user,
                QuestionListOutput,
                ErrorCode.INTERVIEW_QUESTION_GENERATION_FAILED,
                "方向题生成失败：",
            )
            questions = self._convert(result)
            if not questions:
                return self._fallback_questions(skill, question_count)
            return self._cap(questions, question_count)
        except BusinessException:
            raise
        except Exception:
            logger.exception("direction question generation failed; using fallback")
            return self._fallback_questions(skill, question_count)

    def _convert(self, output: QuestionListOutput) -> list[PlannedInterviewQuestion]:
        questions: list[PlannedInterviewQuestion] = []
        for item in output.questions or []:
            if item is None or item.question is None or not item.question.strip():
                continue
            question_type = (
                item.type.upper()
                if item.type is not None and item.type.strip()
                else DEFAULT_QUESTION_TYPE
            )
            questions.append(
                PlannedInterviewQuestion(
                    question=item.question,
                    type=question_type,
                    category=item.category,
                    topic_summary=item.topicSummary,
                )
            )
        return questions

    @staticmethod
    def _cap(
        questions: list[PlannedInterviewQuestion],
        max_main_count: int,
    ) -> list[PlannedInterviewQuestion]:
        return questions[:max_main_count]

    def _fallback_questions(
        self,
        skill: ResolvedSkill,
        count: int,
    ) -> list[PlannedInterviewQuestion]:
        questions: list[PlannedInterviewQuestion] = []
        if skill.categories:
            for generated in range(count):
                category = skill.categories[generated % len(skill.categories)]
                question = f'请谈谈你在"{category.label}"方向的技术理解和实践经验。'
                self._append_fallback(
                    questions,
                    question,
                    category.key,
                    category.label,
                )
            return questions
        for index in range(count):
            question, question_type, category_label = GENERIC_FALLBACK_QUESTIONS[
                index % len(GENERIC_FALLBACK_QUESTIONS)
            ]
            self._append_fallback(
                questions,
                (
                    question
                    if index < len(GENERIC_FALLBACK_QUESTIONS)
                    else f"{question} 请换一个案例说明。"
                ),
                question_type,
                category_label,
            )
        return questions

    def _append_fallback(
        self,
        questions: list[PlannedInterviewQuestion],
        question: str,
        question_type: str,
        category: str,
    ) -> None:
        questions.append(
            PlannedInterviewQuestion(
                question=question,
                type=question_type,
                category=category,
            )
        )

    @staticmethod
    def _merge(
        first: list[PlannedInterviewQuestion],
        second: list[PlannedInterviewQuestion],
    ) -> list[PlannedInterviewQuestion]:
        if not second:
            return first
        if not first:
            return second
        return [*first, *second]

    def _historical_section(
        self,
        historical: list[HistoricalQuestion],
    ) -> str:
        if not historical:
            return "暂无历史提问"
        grouped: dict[str, list[str]] = {}
        for item in historical:
            question_type = (
                item.type if item.type is not None and item.type.strip() else DEFAULT_QUESTION_TYPE
            )
            summary = item.topic_summary
            if summary is None or not summary.strip():
                summary = f"{item.question[:30]}…" if len(item.question) > 30 else item.question
            grouped.setdefault(question_type, []).append(summary)
        lines = ["已考过的知识点（避免重复出题）："]
        for key in stable_key_order(list(grouped)):
            assert key is not None
            lines.append(f"- {key}: {', '.join(grouped[key])}")
        return "\n".join(lines) + "\n"

    def _jd_section(self, source_jd: str | None) -> str:
        if source_jd is None or not source_jd.strip():
            return ""
        sanitized = self._sanitizer.sanitize(source_jd) or ""
        return (
            f"{DATA_BOUNDARY_INSTRUCTION}\n"
            "## 职位描述（JD）\n"
            "根据以下 JD 关键要求出题，确保题目与岗位实际需求相关：\n"
            + self._sanitizer.wrap_with_delimiters("jd", sanitized)
        )

    def _persona_section(self, skill: ResolvedSkill) -> str:
        if skill.persona is None or not skill.persona.strip():
            return ""
        return (
            "\n\n# Skill Persona\n"
            "以下内容来自当前面试方向的 SKILL.md，请作为面试官角色、风格与出题约束：\n"
            + self._sanitizer.wrap_with_delimiters(
                "skill_persona",
                skill.persona,
            )
        )


class JdParseService:
    def __init__(
        self,
        registry: LlmProviderRegistry,
        structured: StructuredOutputInvoker,
        prompts: PromptRepository,
        sanitizer: PromptSanitizer,
        skills: InterviewSkillLibrary,
    ) -> None:
        self._registry = registry
        self._structured = structured
        self._prompts = prompts
        self._sanitizer = sanitizer
        self._skills = skills

    async def parse(self, jd_text: str | None) -> list[CategoryRequest]:
        if jd_text is None or len(jd_text) < 50:
            raise BusinessException(
                ErrorCode.BAD_REQUEST,
                "JD 内容太少（至少 50 字），请补充后重试",
            )
        system = (
            self._prompts.render(
                "jd-parse-system.st",
                {"referenceFileList": self._skills.reference_file_list()},
            )
            + "\n\n"
            + JD_OUTPUT_FORMAT
        )
        sanitized = self._sanitizer.sanitize(jd_text) or ""
        user = f"{DATA_BOUNDARY_INSTRUCTION}\n职位描述：\n" + self._sanitizer.wrap_with_delimiters(
            "jd", sanitized
        )
        result = await self._structured.invoke(
            await self._registry.get_chat(),
            system,
            user,
            JdCategoryListOutput,
            ErrorCode.AI_SERVICE_ERROR,
            "JD 解析失败：",
            tools=(self._skills.tool_definition(),),
        )
        if not result.categories:
            raise BusinessException(
                ErrorCode.AI_SERVICE_ERROR,
                "JD 解析结果为空，请重试",
            )
        return [
            CategoryRequest(
                key=item.key,
                label=item.label,
                priority=item.priority,
                ref=item.ref,
                shared=item.shared,
            )
            for item in result.categories
        ]
