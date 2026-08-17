from __future__ import annotations

from pydantic import field_validator

from interview_guide.common.api.models import CamelModel


def java_trim(value: str) -> str:
    start = 0
    end = len(value)
    while start < end and ord(value[start]) <= 0x20:
        start += 1
    while end > start and ord(value[end - 1]) <= 0x20:
        end -= 1
    return value[start:end]


class QueryRequest(CamelModel):
    knowledge_base_ids: list[int | None]
    question: str

    @field_validator("knowledge_base_ids", mode="before")
    @classmethod
    def validate_knowledge_base_ids(cls, value: object) -> object:
        if value is None or value == []:
            raise ValueError("至少选择一个知识库")
        return value

    @field_validator("question", mode="before")
    @classmethod
    def validate_question(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not java_trim(value)):
            raise ValueError("问题不能为空")
        return value


class QueryResponse(CamelModel):
    answer: str
    knowledge_base_id: int | None
    knowledge_base_name: str
