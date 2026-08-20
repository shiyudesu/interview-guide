from __future__ import annotations

from pydantic import field_validator

from interview_guide.common.api.models import CamelModel


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
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError("问题不能为空")
        return value


class QueryResponse(CamelModel):
    answer: str
    knowledge_base_id: int | None
    knowledge_base_name: str
