from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from interview_guide.common.api.models import CamelModel


class VoiceSessionStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VoiceInterviewPhase(StrEnum):
    INTRO = "INTRO"
    TECH = "TECH"
    PROJECT = "PROJECT"
    HR = "HR"
    COMPLETED = "COMPLETED"


class VoiceEvaluateStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CreateVoiceSessionRequest(CamelModel):
    role_type: str | None = None
    skill_id: str | None = None
    difficulty: str | None = None
    custom_jd_text: str | None = None
    resume_id: int | None = None
    intro_enabled: bool | None = False
    tech_enabled: bool | None = True
    project_enabled: bool | None = True
    hr_enabled: bool | None = True
    planned_duration: int | None = 30
    llm_provider: str | None = None


class VoiceSessionResponse(CamelModel):
    session_id: int
    role_type: str
    current_phase: str
    status: str
    start_time: datetime | None
    planned_duration: int | None
    web_socket_url: str


class VoiceSessionMeta(CamelModel):
    session_id: int
    role_type: str
    status: str
    current_phase: str
    created_at: datetime | None
    updated_at: datetime | None
    actual_duration: int | None
    message_count: int
    evaluate_status: str | None
    evaluate_error: str | None


class VoiceInterviewMessageResponse(CamelModel):
    id: int
    session_id: int | None
    message_type: str
    phase: str | None
    user_recognized_text: str | None
    ai_generated_text: str | None
    timestamp: datetime | None
    sequence_num: int | None


class VoiceAnswerDetail(CamelModel):
    question_index: int
    question: str
    category: str | None
    user_answer: str | None
    score: int
    feedback: str | None
    reference_answer: str | None
    key_points: list[str] | None


class VoiceEvaluationDetail(CamelModel):
    session_id: int | None
    total_questions: int
    overall_score: int | None
    overall_feedback: str | None
    strengths: list[str]
    improvements: list[str]
    answers: list[VoiceAnswerDetail]


class VoiceEvaluationStatusResponse(CamelModel):
    evaluate_status: str | None
    evaluate_error: str | None = None
    evaluate_status_updated_at: datetime | None = None
    evaluation: VoiceEvaluationDetail | None = None
