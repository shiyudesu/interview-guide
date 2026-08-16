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
