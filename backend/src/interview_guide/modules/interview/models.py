from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from interview_guide.common.api.models import CamelModel


class InterviewSessionStatus(StrEnum):
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    EVALUATED = "EVALUATED"


class EvaluateStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CategoryRequest(CamelModel):
    key: str | None = None
    label: str | None = None
    priority: str | None = None
    ref: str | None = None
    shared: bool | None = None


class CreateInterviewRequest(CamelModel):
    resume_text: str | None = None
    question_count: int = 0
    resume_id: int | None = None
    force_create: bool | None = None
    llm_provider: str | None = None
    skill_id: str | None = None
    difficulty: str | None = None
    custom_categories: list[CategoryRequest] | None = None
    jd_text: str | None = None
    request_id: str | None = None


class InterviewQuestion(CamelModel):
    question_index: int
    question: str
    type: str
    category: str | None
    topic_summary: str | None = None
    user_answer: str | None = None
    score: int | None = None
    feedback: str | None = None
    is_follow_up: bool = False
    parent_question_index: int | None = None
    reference_answer: str | None = None
    key_points: list[str] | None = None
    scoring_rubric: str | None = None
    source_context: str | None = None

    def with_answer(self, answer: str | None) -> InterviewQuestion:
        return self.model_copy(update={"user_answer": answer})


class InterviewSessionDTO(CamelModel):
    session_id: str
    resume_text: str
    total_questions: int
    current_question_index: int
    questions: list[InterviewQuestion]
    status: InterviewSessionStatus
    knowledge_base_id: int | None
    interview_category: str | None


class SessionListItemDTO(CamelModel):
    session_id: str
    skill_id: str | None
    difficulty: str | None
    resume_id: int | None
    total_questions: int
    status: str | None
    evaluate_status: str | None
    evaluate_error: str | None
    overall_score: int | None
    source_type: str | None
    knowledge_base_id: int | None
    interview_category: str | None
    created_at: datetime
    completed_at: datetime | None


class SubmitAnswerResponse(CamelModel):
    has_next_question: bool
    next_question: InterviewQuestion | None
    current_index: int
    total_questions: int


class CategoryScore(CamelModel):
    category: str | None
    score: int
    question_count: int


class QuestionEvaluation(CamelModel):
    question_index: int
    question: str
    category: str | None
    user_answer: str | None
    score: int
    feedback: str


class ReferenceAnswer(CamelModel):
    question_index: int
    question: str
    reference_answer: str
    key_points: list[str]


class InterviewReportDTO(CamelModel):
    session_id: str
    total_questions: int
    overall_score: int
    category_scores: list[CategoryScore]
    question_details: list[QuestionEvaluation]
    overall_feedback: str
    strengths: list[str]
    improvements: list[str]
    reference_answers: list[ReferenceAnswer]


class AnswerDetailDTO(CamelModel):
    question_index: int | None
    question: str | None
    category: str | None
    user_answer: str | None
    score: int
    feedback: str | None
    reference_answer: str | None
    key_points: list[str] | None
    answered_at: datetime | None


class InterviewDetailDTO(CamelModel):
    id: int
    session_id: str
    total_questions: int | None
    status: str
    evaluate_status: str | None
    evaluate_error: str | None
    overall_score: int | None
    source_type: str | None
    knowledge_base_id: int | None
    overall_feedback: str | None
    created_at: datetime
    completed_at: datetime | None
    questions: list[object] | None
    strengths: list[str] | None
    improvements: list[str] | None
    reference_answers: list[object] | None
    answers: list[AnswerDetailDTO]


class HistoricalQuestion(CamelModel):
    question: str
    type: str | None
    topic_summary: str | None
