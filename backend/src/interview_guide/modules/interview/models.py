from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from interview_guide.common.api.models import CamelModel, normalize_request_id, to_camel


class InterviewChannel(StrEnum):
    TEXT = "TEXT"
    KNOWLEDGE_BASE = "KNOWLEDGE_BASE"
    VOICE = "VOICE"


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


class QuestionKind(StrEnum):
    MAIN = "MAIN"
    FOLLOW_UP = "FOLLOW_UP"


class TurnAction(StrEnum):
    FOLLOW_UP = "FOLLOW_UP"
    NEXT_MAIN = "NEXT_MAIN"
    COMPLETE = "COMPLETE"


class TurnDecisionStatus(StrEnum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FALLBACK = "FALLBACK"
    FAILED = "FAILED"


class CategoryRequest(CamelModel):
    key: str | None = None
    label: str | None = None
    priority: str | None = None
    ref: str | None = None
    shared: bool | None = None


class CreateInterviewRequest(CamelModel):
    resume_text: str | None = None
    question_count: int = Field(default=0, ge=1, le=30)
    resume_id: int | None = None
    force_create: bool | None = None
    llm_provider: str | None = None
    skill_id: str | None = None
    difficulty: str | None = None
    custom_categories: list[CategoryRequest] | None = None
    jd_text: str | None = None
    request_id: str | None = None

    @model_validator(mode="after")
    def validate_request_id(self) -> CreateInterviewRequest:
        self.request_id = normalize_request_id(self.request_id)
        return self


class PlannedInterviewQuestion(CamelModel):
    question: str
    type: str
    category: str | None = None
    topic_summary: str | None = None
    phase: str | None = None
    reference_answer: str | None = None
    key_points: list[str] | None = None
    scoring_rubric: str | None = None
    source_context: str | None = None
    source_question_id: int | None = None


class InterviewQuestionDTO(CamelModel):
    question_id: UUID
    kind: QuestionKind
    parent_question_id: UUID | None
    question: str
    type: str
    category: str | None
    topic_summary: str | None = None
    phase: str | None = None


class InterviewTurnDTO(CamelModel):
    turn_id: UUID
    question_id: UUID
    question: InterviewQuestionDTO
    answer: str | None
    action: TurnAction | None
    acknowledgement: str | None
    next_question_id: UUID | None
    decision_status: TurnDecisionStatus
    answered_at: datetime
    decided_at: datetime | None


class InterviewProgressDTO(CamelModel):
    completed_main_questions: int
    planned_main_questions: int
    follow_ups_used_for_current_main: int
    max_follow_ups_per_main: int


class InterviewSessionDTO(CamelModel):
    session_id: str
    channel: InterviewChannel
    status: InterviewSessionStatus
    current_question: InterviewQuestionDTO | None
    turns: list[InterviewTurnDTO]
    progress: InterviewProgressDTO
    knowledge_base_id: int | None
    interview_category: str | None


class SessionListItemDTO(CamelModel):
    session_id: str
    channel: InterviewChannel
    skill_id: str | None
    difficulty: str | None
    resume_id: int | None
    planned_main_questions: int
    answered_main_questions: int
    status: str | None
    evaluate_status: str | None
    evaluate_error: str | None
    overall_score: int | None
    knowledge_base_id: int | None
    interview_category: str | None
    created_at: datetime
    completed_at: datetime | None


class SubmitTurnRequest(CamelModel):
    request_id: str
    question_id: UUID
    answer: str | None = None

    @model_validator(mode="after")
    def validate_request(self) -> SubmitTurnRequest:
        normalized = normalize_request_id(self.request_id)
        if normalized is None:
            raise ValueError("requestId不能为空")
        self.request_id = normalized
        if self.answer is not None:
            self.answer = self.answer.replace("\r\n", "\n").replace("\r", "\n")
        return self


class SubmitTurnResponse(CamelModel):
    turn_id: UUID
    action: TurnAction
    acknowledgement: str
    next_question: InterviewQuestionDTO | None
    completed: bool
    progress: InterviewProgressDTO


class TurnDecisionOutput(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=True,
    )

    action: TurnAction
    acknowledgement: str = Field(min_length=1, max_length=80)
    follow_up_question: str | None = Field(default=None, max_length=200)
    reason_code: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=300)
    target_topic: str | None = Field(default=None, max_length=128)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_action(self) -> TurnDecisionOutput:
        if self.action == TurnAction.COMPLETE:
            raise ValueError("模型不能直接决定结束面试")
        if self.action == TurnAction.FOLLOW_UP:
            if self.follow_up_question is None or not self.follow_up_question.strip():
                raise ValueError("FOLLOW_UP必须返回追问")
            self.follow_up_question = self.follow_up_question.strip()
        elif self.follow_up_question is not None:
            self.follow_up_question = None
        return self


class CategoryScore(CamelModel):
    category: str | None
    score: int
    question_count: int


class TurnEvaluationDTO(CamelModel):
    question_id: UUID
    question: str
    answer: str | None
    score: int
    feedback: str
    reference_answer: str | None
    key_points: list[str]


class QuestionGroupEvaluationDTO(CamelModel):
    main_question: TurnEvaluationDTO
    follow_ups: list[TurnEvaluationDTO]
    group_score: int
    group_feedback: str
    category: str | None


class InterviewReportDTO(CamelModel):
    session_id: str
    planned_main_questions: int
    answered_main_questions: int
    overall_score: int
    category_scores: list[CategoryScore]
    question_groups: list[QuestionGroupEvaluationDTO]
    overall_feedback: str
    strengths: list[str]
    improvements: list[str]


class AnswerDetailDTO(CamelModel):
    question_id: UUID
    parent_question_id: UUID | None
    kind: QuestionKind
    question: str
    category: str | None
    user_answer: str | None
    score: int
    feedback: str | None
    reference_answer: str | None
    key_points: list[str]
    answered_at: datetime | None


class InterviewDetailDTO(CamelModel):
    id: int
    session_id: str
    channel: InterviewChannel
    planned_main_questions: int
    status: str
    evaluate_status: str | None
    evaluate_error: str | None
    overall_score: int | None
    knowledge_base_id: int | None
    overall_feedback: str | None
    created_at: datetime
    completed_at: datetime | None
    strengths: list[str]
    improvements: list[str]
    answers: list[AnswerDetailDTO]


class HistoricalQuestion(CamelModel):
    question: str
    type: str | None
    topic_summary: str | None
