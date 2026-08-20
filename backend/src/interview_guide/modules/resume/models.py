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
    analyses: list[object]
    interviews: list[object]


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
