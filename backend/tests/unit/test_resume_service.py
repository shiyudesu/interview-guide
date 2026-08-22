from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from interview_guide.common.db.models import InterviewSession, Resume, ResumeAnalysis
from interview_guide.infrastructure.storage.s3 import S3Storage
from interview_guide.modules.resume.service import ResumeService


class FakeResumeRepository:
    def __init__(
        self,
        resume: Resume,
        analyses: list[ResumeAnalysis],
        interviews: list[InterviewSession],
    ) -> None:
        self._resume = resume
        self._analyses = analyses
        self._interviews = interviews

    async def get(self, resume_id: int) -> Resume | None:
        return self._resume if self._resume.id == resume_id else None

    async def analyses(self, resume_id: int) -> list[ResumeAnalysis]:
        assert resume_id == self._resume.id
        return self._analyses

    async def interviews(self, resume_id: int) -> list[InterviewSession]:
        assert resume_id == self._resume.id
        return self._interviews


@pytest.mark.asyncio
async def test_resume_detail_preserves_typed_analysis_and_interview_contract() -> None:
    timestamp = datetime(2026, 8, 22, 10, 30)
    resume = Resume(
        id=7,
        access_count=1,
        analyze_error=None,
        analyze_status="COMPLETED",
        content_type="application/pdf",
        file_hash="hash",
        file_size=128,
        original_filename="resume.pdf",
        resume_text="Python backend engineer",
        storage_key="resumes/file.pdf",
        storage_url="http://storage/resumes/file.pdf",
        uploaded_at=timestamp,
    )
    analysis = ResumeAnalysis(
        id=11,
        analyzed_at=timestamp,
        content_score=13,
        expression_score=8,
        overall_score=86,
        project_score=35,
        skill_match_score=18,
        strengths_json='["工程经验扎实"]',
        structure_score=12,
        suggestions_json=(
            '[{"category":"项目","priority":"高","issue":"缺少量化",'
            '"recommendation":"补充性能指标"}]'
        ),
        summary="整体较强",
        resume_id=resume.id,
    )
    interview = InterviewSession(
        id=19,
        channel="TEXT",
        completed_at=timestamp,
        created_at=timestamp,
        evaluate_error=None,
        evaluate_status="COMPLETED",
        improvements_json='["补充取舍分析"]',
        max_follow_ups_per_main=1,
        overall_feedback="回答完整",
        overall_score=88,
        planned_main_question_count=6,
        resume_id=resume.id,
        session_id="session-contract",
        status="EVALUATED",
        strengths_json='["表达清晰"]',
    )
    service = ResumeService(
        cast(AsyncSession, object()),
        cast(S3Storage, object()),
    )
    service._repository = cast(Any, FakeResumeRepository(resume, [analysis], [interview]))

    detail = await service.detail(resume.id)
    document = detail.model_dump(mode="json", by_alias=True)

    assert document["analyses"] == [
        {
            "id": 11,
            "overallScore": 86,
            "contentScore": 13,
            "structureScore": 12,
            "skillMatchScore": 18,
            "expressionScore": 8,
            "projectScore": 35,
            "summary": "整体较强",
            "analyzedAt": "2026-08-22T10:30:00",
            "strengths": ["工程经验扎实"],
            "suggestions": [
                {
                    "category": "项目",
                    "priority": "高",
                    "issue": "缺少量化",
                    "recommendation": "补充性能指标",
                }
            ],
        }
    ]
    assert document["interviews"] == [
        {
            "id": 19,
            "sessionId": "session-contract",
            "channel": "TEXT",
            "plannedMainQuestions": 6,
            "status": "EVALUATED",
            "evaluateStatus": "COMPLETED",
            "evaluateError": None,
            "overallScore": 88,
            "overallFeedback": "回答完整",
            "createdAt": "2026-08-22T10:30:00",
            "completedAt": "2026-08-22T10:30:00",
            "strengths": ["表达清晰"],
            "improvements": ["补充取舍分析"],
        }
    ]
