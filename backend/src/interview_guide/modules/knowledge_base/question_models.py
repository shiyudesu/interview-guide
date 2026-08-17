from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import field_validator, model_validator

from interview_guide.common.api.models import CamelModel


class KnowledgeBaseQuestionStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    STALE = "STALE"


class QuestionGenStatus(StrEnum):
    NONE = "NONE"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class KnowledgeBaseQuestionFollowUp(CamelModel):
    question: str | None = None
    reference_answer: str | None = None
    key_points: list[str | None] | None = None
    scoring_rubric: str | None = None


class KnowledgeBaseQuestionDTO(CamelModel):
    id: int
    knowledge_base_id: int | None
    knowledge_base_name: str | None
    skill_id: str
    difficulty: str | None
    type: str | None
    category: str | None
    question: str
    topic_summary: str | None
    reference_answer: str | None
    key_points: list[str]
    scoring_rubric: str | None
    follow_ups: list[KnowledgeBaseQuestionFollowUp]
    source_context: str | None
    status: KnowledgeBaseQuestionStatus
    created_at: datetime
    updated_at: datetime


class GenerateKnowledgeBaseQuestionsRequest(CamelModel):
    difficulty: str | None = None
    question_count: int = 0
    follow_up_count: int | None = None
    category_limit: int | None = None
    llm_provider: str | None = None

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, value: str | None) -> str | None:
        if value is not None and value not in {"junior", "mid", "senior"}:
            raise ValueError("题目难度不合法")
        return value

    @model_validator(mode="after")
    def validate_limits(self) -> GenerateKnowledgeBaseQuestionsRequest:
        if self.question_count < 1:
            raise ValueError("题目数量最少1题")
        if self.question_count > 30:
            raise ValueError("题目数量最多30题")
        if self.follow_up_count is not None and self.follow_up_count < 0:
            raise ValueError("追问数量不能小于0")
        if self.follow_up_count is not None and self.follow_up_count > 5:
            raise ValueError("每题追问最多5个")
        if self.category_limit is None:
            raise ValueError("方向数量不能为空")
        if self.category_limit < 1:
            raise ValueError("方向数最少1个")
        if self.category_limit > 5:
            raise ValueError("方向数最多5个")
        if self.llm_provider is not None and len(self.llm_provider) > 64:
            raise ValueError("模型提供商标识过长")
        return self


class QuestionGenerationConfig(CamelModel):
    difficulty: str
    question_count: int
    follow_up_count: int
    category_limit: int
    llm_provider: str | None


class QuestionGenStatusResponse(CamelModel):
    knowledge_base_id: int
    question_gen_status: QuestionGenStatus
    question_gen_task_id: str | None
    question_gen_config: QuestionGenerationConfig | None
    saved_count: int
    skipped_count: int
    message: str | None
    error: str | None
    updated_at: datetime | None


class CreateKnowledgeBaseQuestionRequest(CamelModel):
    difficulty: str | None = None
    type: str | None = None
    category: str
    question: str
    topic_summary: str | None = None
    reference_answer: str | None = None
    key_points: list[str | None] | None = None
    scoring_rubric: str | None = None
    follow_ups: list[KnowledgeBaseQuestionFollowUp | None] | None = None
    source_context: str | None = None
    status: KnowledgeBaseQuestionStatus | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_required_text(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        category = value.get("category")
        if category is None or not isinstance(category, str) or not category.strip():
            raise ValueError("面试方向不能为空")
        question = value.get("question")
        if question is None or not isinstance(question, str) or not question.strip():
            raise ValueError("题干不能为空")
        return value


class UpdateKnowledgeBaseQuestionRequest(CamelModel):
    difficulty: str | None = None
    type: str | None = None
    category: str | None = None
    question: str | None = None
    topic_summary: str | None = None
    reference_answer: str | None = None
    key_points: list[str | None] | None = None
    scoring_rubric: str | None = None
    follow_ups: list[KnowledgeBaseQuestionFollowUp | None] | None = None
    source_context: str | None = None
    status: KnowledgeBaseQuestionStatus | None = None


class UpdateKnowledgeBaseQuestionStatusRequest(CamelModel):
    status: KnowledgeBaseQuestionStatus | None = None

    @model_validator(mode="after")
    def validate_status(self) -> UpdateKnowledgeBaseQuestionStatusRequest:
        if self.status is None:
            raise ValueError("题目状态不能为空")
        return self


class CategoryCount(CamelModel):
    category: str
    count: int


class CreateKnowledgeBaseInterviewRequest(CamelModel):
    knowledge_base_id: int | None = None
    category: str | None = None
    difficulty: str | None = None
    main_question_count: int = 0
    follow_up_count: int = 0
    llm_provider: str | None = None

    @model_validator(mode="after")
    def validate_request(self) -> CreateKnowledgeBaseInterviewRequest:
        if self.knowledge_base_id is None:
            raise ValueError("知识库不能为空")
        if self.main_question_count < 1:
            raise ValueError("主问题数量最少1题")
        if self.main_question_count > 20:
            raise ValueError("主问题数量最多20题")
        if self.follow_up_count < 0:
            raise ValueError("追问数量不能小于0")
        if self.follow_up_count > 5:
            raise ValueError("每题追问最多5个")
        return self


class InterviewCategoryCapacity(CamelModel):
    category: str
    available_question_count: int


class InterviewFollowUpCapacity(CamelModel):
    follow_up_count: int
    available_question_count: int
    selectable: bool


class KnowledgeBaseInterviewCapacityResponse(CamelModel):
    knowledge_base_id: int
    category: str | None
    difficulty: str
    main_question_count: int
    categories: list[InterviewCategoryCapacity]
    follow_up_options: list[InterviewFollowUpCapacity]


class GeneratedQuestionFollowUp(CamelModel):
    question: str | None = None
    reference_answer: str | None = None
    key_points: list[str | None] | None = None
    scoring_rubric: str | None = None


class GeneratedQuestion(CamelModel):
    category: str | None = None
    type: str | None = None
    question: str | None = None
    topic_summary: str | None = None
    reference_answer: str | None = None
    key_points: list[str | None] | None = None
    scoring_rubric: str | None = None
    follow_ups: list[GeneratedQuestionFollowUp | None] | None = None


class GeneratedQuestionList(CamelModel):
    questions: list[GeneratedQuestion | None] | None = None
