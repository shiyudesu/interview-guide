from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.prompts import PromptRepository
from interview_guide.common.ai.structured import (
    StructuredOutputInvoker,
    java_bean_output_format,
)
from interview_guide.common.errors import ErrorCode
from interview_guide.modules.interview.models import (
    CategoryScore,
    InterviewQuestion,
    InterviewReportDTO,
    QuestionEvaluation,
    ReferenceAnswer,
)
from interview_guide.modules.interview.question import (
    InterviewSkillLibrary,
    java_hashmap_key_order,
)

MAX_REFERENCE_CONTEXT_CHARS = 6_000
logger = logging.getLogger(__name__)
BATCH_OUTPUT_FORMAT = java_bean_output_format(
    {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "improvements": {
                "type": "array",
                "items": {"type": "string"},
            },
            "overallFeedback": {"type": "string"},
            "overallScore": {"type": "integer", "format": "int32"},
            "questionEvaluations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "feedback": {"type": "string"},
                        "keyPoints": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "questionIndex": {
                            "type": "integer",
                            "format": "int32",
                        },
                        "referenceAnswer": {"type": "string"},
                        "score": {"type": "integer", "format": "int32"},
                    },
                    "required": [
                        "feedback",
                        "keyPoints",
                        "questionIndex",
                        "referenceAnswer",
                        "score",
                    ],
                    "additionalProperties": False,
                },
            },
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "improvements",
            "overallFeedback",
            "overallScore",
            "questionEvaluations",
            "strengths",
        ],
        "additionalProperties": False,
    }
)
SUMMARY_OUTPUT_FORMAT = java_bean_output_format(
    {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "improvements": {
                "type": "array",
                "items": {"type": "string"},
            },
            "overallFeedback": {"type": "string"},
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["improvements", "overallFeedback", "strengths"],
        "additionalProperties": False,
    }
)


class QuestionEvaluationOutput(BaseModel):
    questionIndex: int = 0
    score: int = 0
    feedback: str | None = None
    referenceAnswer: str | None = None
    keyPoints: list[str] | None = None


class BatchReportOutput(BaseModel):
    overallScore: int = 0
    overallFeedback: str | None = None
    strengths: list[str | None] | None = None
    improvements: list[str | None] | None = None
    questionEvaluations: list[QuestionEvaluationOutput | None] | None = None


class SummaryOutput(BaseModel):
    overallFeedback: str | None = None
    strengths: list[str | None] | None = None
    improvements: list[str | None] | None = None


@dataclass(frozen=True)
class QaRecord:
    question_index: int
    question: str
    category: str | None
    user_answer: str | None


@dataclass(frozen=True)
class BatchResult:
    start_index: int
    end_index: int
    report: BatchReportOutput | None


class UnifiedEvaluationService:
    def __init__(
        self,
        structured: StructuredOutputInvoker,
        prompts: PromptRepository,
        *,
        batch_size: int = 8,
        tools: Sequence[dict[str, object]] | None = None,
    ) -> None:
        self._structured = structured
        self._prompts = prompts
        self._batch_size = max(1, batch_size)
        self._tools = tools

    async def evaluate(
        self,
        provider: ProviderConfig,
        session_id: str,
        records: list[QaRecord],
        resume_text: str | None,
        reference_context: str | None,
    ) -> InterviewReportDTO:
        resume_context = resume_text or ""
        if len(resume_context) > 3_000:
            resume_context = resume_context[:3_000] + "\n...(简历内容过长，已截断)"
        reference = (reference_context or "").strip()
        if len(reference) > MAX_REFERENCE_CONTEXT_CHARS:
            reference = reference[:MAX_REFERENCE_CONTEXT_CHARS] + "\n...(参考基线过长，已截断)"
        batches: list[BatchResult] = []
        for start in range(0, len(records), self._batch_size):
            end = min(start + self._batch_size, len(records))
            report = await self._evaluate_batch(
                provider,
                resume_context,
                reference,
                records[start:end],
            )
            batches.append(BatchResult(start, end, report))
        evaluations = self._merge_evaluations(batches)
        fallback_feedback = self._merge_feedback(batches)
        fallback_strengths = self._merge_items(batches, strengths=True)
        fallback_improvements = self._merge_items(batches, strengths=False)
        summary = await self._summarize(
            provider,
            resume_context,
            reference,
            records,
            evaluations,
            fallback_feedback,
            fallback_strengths,
            fallback_improvements,
        )
        return self._build_report(
            session_id,
            records,
            evaluations,
            summary.overallFeedback or fallback_feedback,
            self._sanitize_items(summary.strengths, fallback_strengths),
            self._sanitize_items(summary.improvements, fallback_improvements),
        )

    async def _evaluate_batch(
        self,
        provider: ProviderConfig,
        resume_context: str,
        reference_context: str,
        records: list[QaRecord],
    ) -> BatchReportOutput | None:
        system = (
            self._prompts.render("interview-evaluation-system.st") + "\n\n" + BATCH_OUTPUT_FORMAT
        )
        qa_records = "".join(
            f"问题{item.question_index + 1} "
            f"[{self._java_string(item.category)}]: {item.question}\n"
            f"回答: {item.user_answer if item.user_answer is not None else '(未回答)'}\n\n"
            for item in records
        )
        user = self._prompts.render(
            "interview-evaluation-user.st",
            {
                "resumeText": resume_context,
                "qaRecords": qa_records,
                "referenceContext": reference_context or "无",
            },
        )
        try:
            return await self._structured.invoke(
                provider,
                system,
                user,
                BatchReportOutput,
                ErrorCode.INTERVIEW_EVALUATION_FAILED,
                "批次评估失败：",
                tools=self._tools,
            )
        except Exception:
            logger.exception("interview evaluation batch failed")
            return None

    async def _summarize(
        self,
        provider: ProviderConfig,
        resume_context: str,
        reference_context: str,
        records: list[QaRecord],
        evaluations: list[QuestionEvaluationOutput],
        fallback_feedback: str,
        fallback_strengths: list[str],
        fallback_improvements: list[str],
    ) -> SummaryOutput:
        system = (
            self._prompts.render("interview-evaluation-summary-system.st")
            + "\n\n"
            + SUMMARY_OUTPUT_FORMAT
        )
        user = self._prompts.render(
            "interview-evaluation-summary-user.st",
            {
                "resumeText": resume_context,
                "referenceContext": reference_context or "无",
                "categorySummary": self._category_summary(records, evaluations),
                "questionHighlights": self._question_highlights(
                    records,
                    evaluations,
                ),
                "fallbackOverallFeedback": fallback_feedback,
                "fallbackStrengths": "\n".join(fallback_strengths),
                "fallbackImprovements": "\n".join(fallback_improvements),
            },
        )
        try:
            return await self._structured.invoke(
                provider,
                system,
                user,
                SummaryOutput,
                ErrorCode.INTERVIEW_EVALUATION_FAILED,
                "总结评估失败：",
                tools=self._tools,
            )
        except Exception:
            logger.warning(
                "interview evaluation summary failed; using batch fallback",
                exc_info=True,
            )
            return SummaryOutput(
                overallFeedback=fallback_feedback,
                strengths=fallback_strengths,
                improvements=fallback_improvements,
            )

    @staticmethod
    def _merge_evaluations(
        batches: list[BatchResult],
    ) -> list[QuestionEvaluationOutput]:
        merged: list[QuestionEvaluationOutput] = []
        for batch in batches:
            expected = batch.end_index - batch.start_index
            current = (
                batch.report.questionEvaluations
                if batch.report is not None and batch.report.questionEvaluations
                else []
            )
            for index in range(expected):
                if index < len(current) and current[index] is not None:
                    value = current[index]
                    assert value is not None
                    merged.append(value)
                else:
                    merged.append(
                        QuestionEvaluationOutput(
                            questionIndex=batch.start_index + index,
                            score=0,
                            feedback="该题未成功生成评估结果，系统按 0 分处理。",
                            referenceAnswer="",
                            keyPoints=[],
                        )
                    )
        return merged

    @staticmethod
    def _merge_feedback(batches: list[BatchResult]) -> str:
        values = [
            report.overallFeedback
            for batch in batches
            if (report := batch.report) is not None
            and report.overallFeedback is not None
            and report.overallFeedback.strip()
        ]
        return "\n\n".join(values) if values else "本次面试已完成分批评估，但未生成有效综合评语。"

    @staticmethod
    def _merge_items(
        batches: list[BatchResult],
        *,
        strengths: bool,
    ) -> list[str]:
        values: list[str] = []
        for batch in batches:
            if batch.report is None:
                continue
            raw = batch.report.strengths if strengths else batch.report.improvements
            for item in raw or []:
                if item is not None and item.strip() and item.strip() not in values:
                    values.append(item.strip())
                    if len(values) == 8:
                        return values
        return values

    def _build_report(
        self,
        session_id: str,
        records: list[QaRecord],
        evaluations: list[QuestionEvaluationOutput],
        overall_feedback: str,
        strengths: list[str],
        improvements: list[str],
    ) -> InterviewReportDTO:
        details: list[QuestionEvaluation] = []
        references: list[ReferenceAnswer] = []
        category_scores: dict[str | None, list[int]] = {}
        answered_count = sum(
            item.user_answer is not None and bool(item.user_answer.strip()) for item in records
        )
        for index, record in enumerate(records):
            evaluation = evaluations[index] if index < len(evaluations) else None
            has_answer = record.user_answer is not None and bool(record.user_answer.strip())
            score = evaluation.score if has_answer and evaluation is not None else 0
            feedback = (
                evaluation.feedback
                if evaluation is not None and evaluation.feedback is not None
                else "该题未成功生成评估反馈。"
            )
            reference_answer = (
                evaluation.referenceAnswer
                if evaluation is not None and evaluation.referenceAnswer is not None
                else ""
            )
            key_points = (
                evaluation.keyPoints
                if evaluation is not None and evaluation.keyPoints is not None
                else []
            )
            details.append(
                QuestionEvaluation(
                    question_index=record.question_index,
                    question=record.question,
                    category=record.category,
                    user_answer=record.user_answer,
                    score=score,
                    feedback=feedback,
                )
            )
            references.append(
                ReferenceAnswer(
                    question_index=record.question_index,
                    question=record.question,
                    reference_answer=reference_answer,
                    key_points=key_points,
                )
            )
            category_scores.setdefault(record.category, []).append(score)
        categories = [
            CategoryScore(
                category=category,
                score=int(sum(category_scores[category]) / len(category_scores[category])),
                question_count=len(category_scores[category]),
            )
            for category in java_hashmap_key_order(list(category_scores))
        ]
        overall_score = (
            0 if answered_count == 0 else int(sum(item.score for item in details) / len(details))
        )
        return InterviewReportDTO(
            session_id=session_id,
            total_questions=len(records),
            overall_score=overall_score,
            category_scores=categories,
            question_details=details,
            overall_feedback=overall_feedback,
            strengths=strengths,
            improvements=improvements,
            reference_answers=references,
        )

    @staticmethod
    def _category_summary(
        records: list[QaRecord],
        evaluations: list[QuestionEvaluationOutput],
    ) -> str:
        category_scores: dict[str | None, list[int]] = {}
        for index, record in enumerate(records):
            evaluation = evaluations[index] if index < len(evaluations) else None
            score = 0
            if (
                evaluation is not None
                and record.user_answer is not None
                and record.user_answer.strip()
            ):
                score = evaluation.score
            category_scores.setdefault(record.category, []).append(score)
        return "\n".join(
            sorted(
                f"- {UnifiedEvaluationService._java_string(category)}: "
                f"平均分 {int(sum(scores) / len(scores))}, 题数 {len(scores)}"
                for category, scores in category_scores.items()
            )
        )

    @staticmethod
    def _question_highlights(
        records: list[QaRecord],
        evaluations: list[QuestionEvaluationOutput],
    ) -> str:
        values: list[str] = []
        for index, record in enumerate(records):
            evaluation = evaluations[index] if index < len(evaluations) else None
            score = evaluation.score if evaluation is not None else 0
            feedback = (
                evaluation.feedback
                if evaluation is not None and evaluation.feedback is not None
                else ""
            )
            question = (
                f"{record.question[:50]}..." if len(record.question) > 50 else record.question
            )
            short_feedback = f"{feedback[:80]}..." if len(feedback) > 80 else feedback
            values.append(
                f"- Q{record.question_index + 1} | {question} | "
                f"分数:{score} | 反馈:{short_feedback}"
            )
        return "\n".join(values[:20])

    @staticmethod
    def _sanitize_items(
        primary: list[str | None] | None,
        fallback: list[str],
    ) -> list[str]:
        source: list[str | None] = list(primary) if primary else list(fallback)
        result: list[str] = []
        for item in source:
            if item is not None and item.strip() and item.strip() not in result:
                result.append(item.strip())
                if len(result) == 8:
                    break
        return result

    @staticmethod
    def _java_string(value: object | None) -> str:
        return "null" if value is None else str(value)


class AnswerEvaluationService:
    def __init__(
        self,
        unified: UnifiedEvaluationService,
        skills: InterviewSkillLibrary,
    ) -> None:
        self._unified = unified
        self._skills = skills

    async def evaluate(
        self,
        provider: ProviderConfig,
        session_id: str,
        resume_text: str,
        questions: list[InterviewQuestion],
        skill_id: str | None,
    ) -> InterviewReportDTO:
        records = [
            QaRecord(
                question_index=item.question_index,
                question=item.question,
                category=item.category,
                user_answer=item.user_answer,
            )
            for item in questions
        ]
        reference = self._question_reference_context(questions)
        if not reference.strip():
            reference = self._skills.evaluation_reference_section(skill_id)
        report = await self._unified.evaluate(
            provider,
            session_id,
            records,
            resume_text,
            reference,
        )
        references: list[ReferenceAnswer] = []
        questions_by_index = {item.question_index: item for item in questions}
        for item in report.reference_answers:
            question = questions_by_index.get(item.question_index)
            if (
                question is None
                or question.reference_answer is None
                or not question.reference_answer.strip()
            ):
                references.append(item)
            else:
                references.append(
                    ReferenceAnswer(
                        question_index=item.question_index,
                        question=item.question,
                        reference_answer=question.reference_answer,
                        key_points=question.key_points or [],
                    )
                )
        return report.model_copy(update={"reference_answers": references})

    @staticmethod
    def _question_reference_context(
        questions: list[InterviewQuestion],
    ) -> str:
        values: list[str] = []
        for question in questions:
            if not (
                (question.reference_answer and question.reference_answer.strip())
                or (question.scoring_rubric and question.scoring_rubric.strip())
                or question.key_points
            ):
                continue
            lines = [f"问题{question.question_index + 1}: {question.question}"]
            if question.reference_answer and question.reference_answer.strip():
                lines.append(f"参考答案: {question.reference_answer.strip()}")
            if question.key_points:
                lines.append(f"评分要点: {'；'.join(question.key_points)}")
            if question.scoring_rubric and question.scoring_rubric.strip():
                lines.append(f"评分规则: {question.scoring_rubric.strip()}")
            values.append("\n".join(lines) + "\n")
        return "\n".join(values)
