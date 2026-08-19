from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from interview_guide.modules.knowledge_base.rag_chat_api import (
    rag_chat_sse_data,
    rag_chat_sse_stream,
)
from interview_guide.modules.knowledge_base.rag_chat_models import (
    CreateSessionRequest,
    SendMessageRequest,
    UpdateKnowledgeBasesRequest,
    UpdateTitleRequest,
)


class ExplicitFakeCompleter:
    def __init__(self) -> None:
        self.completions: list[tuple[int, str]] = []

    async def complete_stream_message(
        self,
        message_id: int,
        content: str,
    ) -> None:
        self.completions.append((message_id, content))


@dataclass
class ExplicitFakeChunks:
    chunks: list[str]
    error: Exception | None = None
    closed: bool = False
    yielded: list[str] = field(default_factory=list)

    def __aiter__(self) -> AsyncIterator[str]:
        return self.iterate()

    async def iterate(self) -> AsyncIterator[str]:
        try:
            for chunk in self.chunks:
                self.yielded.append(chunk)
                yield chunk
            if self.error is not None:
                raise self.error
        finally:
            self.closed = True


def test_rag_chat_requests_use_compatibility_validation_messages() -> None:
    with pytest.raises(ValidationError, match="至少选择一个知识库"):
        CreateSessionRequest.model_validate({"knowledgeBaseIds": []})
    with pytest.raises(ValidationError, match="至少选择一个知识库"):
        UpdateKnowledgeBasesRequest.model_validate({"knowledgeBaseIds": []})
    with pytest.raises(ValidationError, match="问题不能为空"):
        SendMessageRequest.model_validate({"question": " \t"})
    with pytest.raises(ValidationError, match="标题不能为空"):
        UpdateTitleRequest.model_validate({"title": "\n"})

    request = CreateSessionRequest.model_validate({"knowledgeBaseIds": [1], "title": "\u00a0"})
    assert request.title == "\u00a0"


def test_rag_chat_sse_escapes_newlines_like_compatibility_controller() -> None:
    assert rag_chat_sse_data("第一行\r\n第二行") == (
        b"data:\xe7\xac\xac\xe4\xb8\x80\xe8\xa1\x8c\\r\\n\xe7\xac\xac\xe4\xba\x8c\xe8\xa1\x8c\n\n"
    )


@pytest.mark.asyncio
async def test_explicit_fake_rag_stream_saves_complete_content() -> None:
    service = ExplicitFakeCompleter()
    chunks = ExplicitFakeChunks(["第一段", "\n第二段"])

    body = rag_chat_sse_stream(service, 7, chunks)  # type: ignore[arg-type]
    output = [chunk async for chunk in body]

    assert output == [
        b"data:\xe7\xac\xac\xe4\xb8\x80\xe6\xae\xb5\n\n",
        (b"data:\\n\xe7\xac\xac\xe4\xba\x8c\xe6\xae\xb5\n\n"),
    ]
    assert service.completions == [(7, "第一段\n第二段")]
    assert chunks.closed is True


@pytest.mark.asyncio
async def test_explicit_fake_rag_stream_error_saves_partial_then_raises() -> None:
    service = ExplicitFakeCompleter()
    chunks = ExplicitFakeChunks(["已生成"], RuntimeError("explicit fake failure"))
    body = rag_chat_sse_stream(service, 8, chunks)  # type: ignore[arg-type]

    assert await anext(body) == b"data:\xe5\xb7\xb2\xe7\x94\x9f\xe6\x88\x90\n\n"
    with pytest.raises(RuntimeError, match="explicit fake failure"):
        await anext(body)

    assert service.completions == [(8, "已生成")]
    assert chunks.closed is True


@pytest.mark.asyncio
async def test_explicit_fake_rag_stream_cancel_keeps_placeholder_incomplete() -> None:
    service = ExplicitFakeCompleter()
    chunks = ExplicitFakeChunks(["部分内容", "不应读取"])
    body = rag_chat_sse_stream(service, 9, chunks)  # type: ignore[arg-type]

    assert await anext(body) == (b"data:\xe9\x83\xa8\xe5\x88\x86\xe5\x86\x85\xe5\xae\xb9\n\n")
    await body.aclose()

    assert service.completions == []
    assert chunks.yielded == ["部分内容"]
    assert chunks.closed is True
