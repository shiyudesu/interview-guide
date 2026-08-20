from __future__ import annotations

from datetime import datetime

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


class KnowledgeBaseItemResponse(CamelModel):
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


class KnowledgeBaseStatisticsResponse(CamelModel):
    total_count: int
    total_question_count: int
    total_access_count: int
    completed_count: int
    processing_count: int


class UploadedKnowledgeBaseResponse(CamelModel):
    id: int
    name: str
    category: str | None = None
    file_size: int | None
    content_length: int
    vector_status: str | None = None


class StorageResponse(CamelModel):
    file_key: str
    file_url: str


class UploadKnowledgeBaseResponse(CamelModel):
    knowledge_base: UploadedKnowledgeBaseResponse
    storage: StorageResponse
    duplicate: bool
