from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import model_validator

from interview_guide.common.api.models import CamelModel, normalize_request_id
from interview_guide.modules.interview.models import InterviewReportDTO


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
    request_id: str | None = None

    @model_validator(mode="after")
    def validate_request(self) -> CreateVoiceSessionRequest:
        duration = self.planned_duration or 30
        if duration < 15 or duration > 60 or duration % 5 != 0:
            raise ValueError("计划面试时长必须是15到60分钟且为5的倍数")
        if not any(
            (
                self.intro_enabled,
                self.tech_enabled,
                self.project_enabled,
                self.hr_enabled,
            )
        ):
            raise ValueError("至少启用一个面试阶段")
        self.request_id = normalize_request_id(self.request_id)
        return self


class VoiceSessionResponse(CamelModel):
    session_id: int
    interview_session_id: str | None = None
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
    overall_score: int | None


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
    evaluation: InterviewReportDTO | None = None
