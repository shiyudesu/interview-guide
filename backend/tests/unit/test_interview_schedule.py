from __future__ import annotations

import pytest
from pydantic import ValidationError

from interview_guide.modules.interview_schedule.models import (
    CreateInterviewRequest,
)


def test_interview_time_accepts_compatibility_minute_and_second_formats() -> None:
    minute = CreateInterviewRequest.model_validate(
        {
            "companyName": "Company",
            "position": "Engineer",
            "interviewTime": "2026-08-20T10:30",
        }
    )
    second = CreateInterviewRequest.model_validate(
        {
            "companyName": "Company",
            "position": "Engineer",
            "interviewTime": "2026-08-20T10:30:45",
        }
    )

    assert minute.interview_time.second == 0
    assert second.interview_time.second == 45


def test_interview_time_rejects_timezone_and_extra_precision() -> None:
    for value in (
        "2026-08-20T10:30:00+08:00",
        "2026-08-20T10:30:00.123",
    ):
        with pytest.raises(ValidationError, match="面试时间格式错误"):
            CreateInterviewRequest.model_validate(
                {
                    "companyName": "Company",
                    "position": "Engineer",
                    "interviewTime": value,
                }
            )
