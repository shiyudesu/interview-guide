from __future__ import annotations

from datetime import datetime

from pydantic import field_validator

from interview_guide.common.api.models import CamelModel
from interview_guide.modules.knowledge_base.models import java_trim


def validate_not_empty(value: object) -> object:
    if value is None or value == []:
        raise ValueError("至少选择一个知识库")
    return value


def validate_not_blank(value: object, message: str) -> object:
    if value is None or (isinstance(value, str) and not java_trim(value)):
        raise ValueError(message)
    return value


class CreateSessionRequest(CamelModel):
    knowledge_base_ids: list[int | None]
    title: str | None = None

    @field_validator("knowledge_base_ids", mode="before")
    @classmethod
    def validate_ids(cls, value: object) -> object:
        return validate_not_empty(value)


class SendMessageRequest(CamelModel):
    question: str

    @field_validator("question", mode="before")
    @classmethod
    def validate_question(cls, value: object) -> object:
        return validate_not_blank(value, "问题不能为空")


class UpdateTitleRequest(CamelModel):
    title: str

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: object) -> object:
        return validate_not_blank(value, "标题不能为空")


class UpdateKnowledgeBasesRequest(CamelModel):
    knowledge_base_ids: list[int | None]

    @field_validator("knowledge_base_ids", mode="before")
    @classmethod
    def validate_ids(cls, value: object) -> object:
        return validate_not_empty(value)


class SessionDTO(CamelModel):
    id: int
    title: str
    knowledge_base_ids: list[int]
    created_at: datetime


class SessionListItemDTO(CamelModel):
    id: int
    title: str
    message_count: int | None
    knowledge_base_names: list[str]
    updated_at: datetime | None
    is_pinned: bool


class KnowledgeBaseListItemDTO(CamelModel):
    id: int
    name: str
    category: str | None
    original_filename: str
    file_size: int | None
    content_type: str | None
    uploaded_at: datetime
    last_accessed_at: datetime | None
    access_count: int | None
    question_count: int | None
    vector_status: str | None
    vector_error: str | None
    chunk_count: int | None
    question_gen_status: str | None
    question_gen_error: str | None


class MessageDTO(CamelModel):
    id: int
    type: str
    content: str
    created_at: datetime


class SessionDetailDTO(CamelModel):
    id: int
    title: str
    knowledge_bases: list[KnowledgeBaseListItemDTO]
    messages: list[MessageDTO]
    created_at: datetime
    updated_at: datetime | None
