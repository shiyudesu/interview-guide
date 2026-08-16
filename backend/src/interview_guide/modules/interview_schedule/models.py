from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import field_validator

from interview_guide.common.api.models import CamelModel

INTERVIEW_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$")


class InterviewStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    RESCHEDULED = "RESCHEDULED"


class CreateInterviewRequest(CamelModel):
    company_name: str
    position: str
    interview_time: datetime
    interview_type: str | None = None
    meeting_link: str | None = None
    round_number: int | None = 1
    interviewer: str | None = None
    notes: str | None = None

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("公司名称不能为空")
        return value

    @field_validator("position")
    @classmethod
    def validate_position(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("岗位不能为空")
        return value

    @field_validator("interview_time", mode="before")
    @classmethod
    def validate_interview_time(cls, value: Any) -> datetime:
        if value is None:
            raise ValueError("面试时间不能为空")
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                raise ValueError("面试时间格式错误")
            return value
        if not isinstance(value, str) or not INTERVIEW_TIME.fullmatch(value):
            raise ValueError("面试时间格式错误")
        format_string = "%Y-%m-%dT%H:%M:%S" if len(value) == 19 else "%Y-%m-%dT%H:%M"
        return datetime.strptime(value, format_string)


class InterviewScheduleResponse(CamelModel):
    company_name: str
    created_at: datetime | None
    id: int
    interview_time: datetime
    interview_type: str | None
    interviewer: str | None
    meeting_link: str | None
    notes: str | None
    position: str
    round_number: int | None
    status: InterviewStatus
    updated_at: datetime | None


class ParseRequest(CamelModel):
    raw_text: str
    source: str | None = None

    @field_validator("raw_text")
    @classmethod
    def validate_raw_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("文本不能为空")
        return value


class ParseResponse(CamelModel):
    confidence: float
    data: CreateInterviewRequest | None
    log: str
    parse_method: str
    success: bool
