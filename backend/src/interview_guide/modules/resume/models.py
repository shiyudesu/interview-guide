from __future__ import annotations

from datetime import datetime

from interview_guide.common.api.models import CamelModel


class ResumeListResponse(CamelModel):
    id: int
    filename: str
    file_size: int | None
    uploaded_at: datetime
    access_count: int | None
    latest_score: int | None
    last_analyzed_at: datetime | None
    interview_count: int
    analyze_status: str | None
    analyze_error: str | None


class ResumeSuggestionResponse(CamelModel):
    category: str
    priority: str
    issue: str
    recommendation: str


class ResumeAnalysisHistoryResponse(CamelModel):
    id: int
    overall_score: int | None
    content_score: int | None
    structure_score: int | None
    skill_match_score: int | None
    expression_score: int | None
    project_score: int | None
    summary: str | None
    analyzed_at: datetime
    strengths: list[str]
    suggestions: list[ResumeSuggestionResponse]


class ResumeInterviewResponse(CamelModel):
    id: int
    session_id: str
    channel: str
    planned_main_questions: int
    status: str | None
    evaluate_status: str | None
    evaluate_error: str | None
    overall_score: int | None
    overall_feedback: str | None
    created_at: datetime
    completed_at: datetime | None
    strengths: list[str]
    improvements: list[str]


class ResumeDetailResponse(CamelModel):
    id: int
    filename: str
    file_size: int | None
    content_type: str | None
    storage_url: str | None
    uploaded_at: datetime
    access_count: int | None
    resume_text: str | None
    analyze_status: str | None
    analyze_error: str | None
    analyses: list[ResumeAnalysisHistoryResponse]
    interviews: list[ResumeInterviewResponse]


class ResumeScoreDetail(CamelModel):
    content_score: int | None
    structure_score: int | None
    skill_match_score: int | None
    expression_score: int | None
    project_score: int | None


class ResumeAnalysisResponse(CamelModel):
    overall_score: int | None
    score_detail: ResumeScoreDetail
    summary: str | None
    strengths: list[object]
    suggestions: list[object]
    original_text: str | None


class UploadedResumeResponse(CamelModel):
    analyze_status: str
    filename: str
    id: int


class ResumeStorageResponse(CamelModel):
    resume_id: int
    file_url: str
    file_key: str


class UploadResumeResponse(CamelModel):
    resume: UploadedResumeResponse | None = None
    analysis: ResumeAnalysisResponse | None = None
    storage: ResumeStorageResponse
    duplicate: bool
