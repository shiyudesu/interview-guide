from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, Field

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.prompts import PromptRepository
from interview_guide.common.ai.structured import StructuredOutputInvoker, structured_output_format
from interview_guide.common.db.models import InterviewQuestionRecord, InterviewTurnRecord
from interview_guide.common.errors import ErrorCode
from interview_guide.modules.interview.models import (
    CategoryScore,
    InterviewReportDTO,
    QuestionGroupEvaluationDTO,
    QuestionKind,
    TurnEvaluationDTO,
)
from interview_guide.modules.interview.repository import SessionAggregate, parse_key_points

logger = logging.getLogger(__name__)
EVALUATION_OUTPUT_FORMAT = structured_output_format(
    {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "overallFeedback": {"type": "string"},
            "strengths": {"type": "array", "items": {"type": "string"}},
            "improvements": {"type": "array", "items": {"type": "string"}},
            "groups": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "mainOrder": {"type": "integer"},
                        "score": {"type": "integer"},
                        "feedback": {"type": "string"},
                        "turns": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "questionId": {"type": "string"},
                                    "score": {"type": "integer"},
                                    "feedback": {"type": "string"},
                                    "referenceAnswer": {"type": "string"},
                                    "keyPoints": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": [
                                    "questionId",
                                    "score",
                                    "feedback",
                                    "referenceAnswer",
                                    "keyPoints",
                                ],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["mainOrder", "score", "feedback", "turns"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["overallFeedback", "strengths", "improvements", "groups"],
        "additionalProperties": False,
    }
)


class TurnEvaluationOutput(BaseModel):
    questionId: UUID
    score: int = Field(ge=0, le=100)
    feedback: str
    referenceAnswer: str
    keyPoints: list[str]


class GroupEvaluationOutput(BaseModel):
    mainOrder: int
    score: int = Field(ge=0, le=100)
    feedback: str
    turns: list[TurnEvaluationOutput]


class EvaluationOutput(BaseModel):
    overallFeedback: str
    strengths: list[str]
    improvements: list[str]
    groups: list[GroupEvaluationOutput]


@dataclass(frozen=True)
class QuestionGroup:
    main: InterviewQuestionRecord
    questions: list[InterviewQuestionRecord]
    turns: dict[UUID, InterviewTurnRecord]


class UnifiedEvaluationService:
    def __init__(
        self,
        structured: StructuredOutputInvoker,
        prompts: PromptRepository,
    ) -> None:
        self._structured = structured
        self._prompts = prompts

    async def evaluate(
        self,
        provider: ProviderConfig,
        aggregate: SessionAggregate,
    ) -> InterviewReportDTO:
        groups = self._answered_groups(aggregate)
        if not groups:
            return InterviewReportDTO(
                session_id=aggregate.session.session_id,
                planned_main_questions=aggregate.session.planned_main_question_count,
                answered_main_questions=0,
                overall_score=0,
                category_scores=[],
                question_groups=[],
                overall_feedback="本次面试没有可评估的回答。",
                strengths=[],
                improvements=[],
            )
        system = (
            self._prompts.render("interview-group-evaluation-system.st")
            + "\n\n"
            + EVALUATION_OUTPUT_FORMAT
        )
        user = self._prompts.render(
            "interview-group-evaluation-user.st",
            {
                "resumeText": aggregate.resume_text[:3000] or "无",
                "questionGroups": self._format_groups(groups),
            },
        )
        output = await self._structured.invoke(
            provider,
            system,
            user,
            EvaluationOutput,
            ErrorCode.INTERVIEW_EVALUATION_FAILED,
            "面试评估失败：",
        )
        return self._report(aggregate, groups, output)

    @staticmethod
    def _answered_groups(aggregate: SessionAggregate) -> list[QuestionGroup]:
        turns = {turn.question_id: turn for turn in aggregate.turns}
        grouped: dict[int, list[InterviewQuestionRecord]] = defaultdict(list)
        for question in aggregate.questions:
            grouped[question.main_order].append(question)
        result: list[QuestionGroup] = []
        for main_order in sorted(grouped):
            questions = sorted(grouped[main_order], key=lambda item: item.follow_up_order)
            main = next(item for item in questions if item.kind == QuestionKind.MAIN.value)
            if not any(question.id in turns for question in questions):
                continue
            result.append(QuestionGroup(main, questions, turns))
        return result

    @staticmethod
    def _format_groups(groups: list[QuestionGroup]) -> str:
        sections: list[str] = []
        for group in groups:
            lines = [
                f"主问题组 mainOrder={group.main.main_order}",
                f"分类：{group.main.category or '综合'}",
                f"参考答案：{group.main.reference_answer or '无'}",
                f"关键点：{'、'.join(parse_key_points(group.main.key_points_json)) or '无'}",
                f"评分规则：{group.main.scoring_rubric or '无'}",
                f"参考上下文：{(group.main.source_context or '无')[:3000]}",
            ]
            for question in group.questions:
                turn = group.turns.get(question.id)
                lines.extend(
                    (
                        f"questionId={question.id}",
                        f"问题：{question.question}",
                        f"回答：{turn.answer if turn is not None and turn.answer else '(未回答)'}",
                    )
                )
            sections.append("\n".join(lines))
        return "\n\n---\n\n".join(sections)

    def _report(
        self,
        aggregate: SessionAggregate,
        groups: list[QuestionGroup],
        output: EvaluationOutput,
    ) -> InterviewReportDTO:
        output_by_order = {item.mainOrder: item for item in output.groups}
        report_groups: list[QuestionGroupEvaluationDTO] = []
        category_scores: dict[str | None, list[int]] = defaultdict(list)
        for group in groups:
            evaluated = output_by_order.get(group.main.main_order)
            turn_outputs = (
                {item.questionId: item for item in evaluated.turns} if evaluated is not None else {}
            )
            children: list[TurnEvaluationDTO] = []
            main_detail: TurnEvaluationDTO | None = None
            for question in group.questions:
                turn = group.turns.get(question.id)
                item = turn_outputs.get(question.id)
                detail = TurnEvaluationDTO(
                    question_id=question.id,
                    question=question.question,
                    answer=turn.answer if turn is not None else None,
                    score=item.score if item is not None else 0,
                    feedback=(item.feedback if item is not None else "该轮未生成有效评估结果。"),
                    reference_answer=(
                        item.referenceAnswer
                        if item is not None and item.referenceAnswer
                        else question.reference_answer
                    ),
                    key_points=(
                        item.keyPoints
                        if item is not None and item.keyPoints
                        else parse_key_points(question.key_points_json)
                    ),
                )
                if question.kind == QuestionKind.MAIN.value:
                    main_detail = detail
                else:
                    children.append(detail)
            assert main_detail is not None
            group_score = evaluated.score if evaluated is not None else 0
            category_scores[group.main.category].append(group_score)
            report_groups.append(
                QuestionGroupEvaluationDTO(
                    main_question=main_detail,
                    follow_ups=children,
                    group_score=group_score,
                    group_feedback=(
                        evaluated.feedback
                        if evaluated is not None
                        else "该主问题组未生成有效评估结果。"
                    ),
                    category=group.main.category,
                )
            )
        scores = [item.group_score for item in report_groups]
        categories = [
            CategoryScore(
                category=category,
                score=int(sum(values) / len(values)),
                question_count=len(values),
            )
            for category, values in sorted(
                category_scores.items(),
                key=lambda item: str(item[0] or ""),
            )
        ]
        return InterviewReportDTO(
            session_id=aggregate.session.session_id,
            planned_main_questions=aggregate.session.planned_main_question_count,
            answered_main_questions=len(report_groups),
            overall_score=int(sum(scores) / len(scores)) if scores else 0,
            category_scores=categories,
            question_groups=report_groups,
            overall_feedback=output.overallFeedback,
            strengths=self._unique(output.strengths),
            improvements=self._unique(output.improvements),
        )

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            normalized = value.strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return result[:8]


def parse_saved_list(value: str | None) -> list[str]:
    if value is None:
        return []
    try:
        document = json.loads(value)
    except ValueError:
        logger.warning("invalid saved report list")
        return []
    return [str(item) for item in document] if isinstance(document, list) else []
