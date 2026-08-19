from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from starlette.responses import Response, StreamingResponse

from interview_guide.common.api.responses import result_response
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.result import Result
from interview_guide.modules.knowledge_base.api import knowledge_base_query_service
from interview_guide.modules.knowledge_base.rag_chat_models import (
    CreateSessionRequest,
    SendMessageRequest,
    UpdateKnowledgeBasesRequest,
    UpdateTitleRequest,
)
from interview_guide.modules.knowledge_base.rag_chat_repository import (
    RagChatRepository,
)
from interview_guide.modules.knowledge_base.rag_chat_service import RagChatService

router = APIRouter(prefix="/api/rag-chat")


def rag_chat_service(request: Request) -> RagChatService:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    settings = request.app.state.settings
    repository = RagChatRepository(
        infrastructure.database.sessions,
        now=datetime.now,
    )
    return RagChatService(
        repository,
        knowledge_base_query_service(request),
        history_enabled=settings.ai_rag_history_enabled,
        history_max_messages=settings.ai_rag_history_max_messages,
    )


ServiceDependency = Annotated[RagChatService, Depends(rag_chat_service)]


def rag_chat_sse_data(content: str) -> bytes:
    escaped = content.replace("\n", "\\n").replace("\r", "\\r")
    return f"data:{escaped}\n\n".encode()


async def rag_chat_sse_stream(
    service: RagChatService,
    message_id: int,
    chunks: AsyncIterator[str],
) -> AsyncIterator[bytes]:
    full_content: list[str] = []
    iterator = chunks.__aiter__()
    try:
        async for chunk in iterator:
            full_content.append(chunk)
            yield rag_chat_sse_data(chunk)
    except (asyncio.CancelledError, GeneratorExit):
        raise
    except Exception as error:
        content = "".join(full_content) if full_content else f"【错误】回答生成失败：{error}"
        await service.complete_stream_message(message_id, content)
        raise
    else:
        await service.complete_stream_message(message_id, "".join(full_content))
    finally:
        close = getattr(iterator, "aclose", None)
        if close is not None:
            await close()


@router.post("/sessions")
async def create_session(
    payload: CreateSessionRequest,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.create_session(payload)))


@router.get("/sessions")
async def list_sessions(service: ServiceDependency) -> Response:
    return result_response(Result.ok(await service.list_sessions()))


@router.get("/sessions/{session_id}")
async def session_detail(
    session_id: int,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.session_detail(session_id)))


@router.put("/sessions/{session_id}/title")
async def update_title(
    session_id: int,
    payload: UpdateTitleRequest,
    service: ServiceDependency,
) -> Response:
    await service.update_title(session_id, payload.title)
    return result_response(Result.ok())


@router.put("/sessions/{session_id}/pin")
async def toggle_pin(
    session_id: int,
    service: ServiceDependency,
) -> Response:
    await service.toggle_pin(session_id)
    return result_response(Result.ok())


@router.put("/sessions/{session_id}/knowledge-bases")
async def update_knowledge_bases(
    session_id: int,
    payload: UpdateKnowledgeBasesRequest,
    service: ServiceDependency,
) -> Response:
    await service.update_knowledge_bases(
        session_id,
        payload.knowledge_base_ids,
    )
    return result_response(Result.ok())


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    service: ServiceDependency,
) -> Response:
    await service.delete_session(session_id)
    return result_response(Result.ok())


@router.post("/sessions/{session_id}/messages/stream")
async def send_message_stream(
    session_id: int,
    payload: SendMessageRequest,
    service: ServiceDependency,
) -> Response:
    message_id = await service.prepare_stream_message(
        session_id,
        payload.question,
    )
    chunks = await service.get_stream_answer(session_id, payload.question)
    return StreamingResponse(
        rag_chat_sse_stream(service, message_id, chunks),
        media_type="text/event-stream",
        headers={"Content-Type": "text/event-stream"},
    )
