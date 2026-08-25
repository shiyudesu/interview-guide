from __future__ import annotations

from fastapi import APIRouter, WebSocket

from interview_guide.modules.auth.dependencies import current_actor
from interview_guide.modules.auth.middleware import request_origin_allowed
from interview_guide.modules.voice_interview.api import build_service
from interview_guide.modules.voice_interview.websocket import VoiceWebSocketRuntime

router = APIRouter()


@router.websocket("/ws/voice-interview/{sessionId}")
async def voice_interview_websocket(
    websocket: WebSocket,
    sessionId: str,
) -> None:
    settings = websocket.app.state.settings
    if not request_origin_allowed(websocket.headers, websocket.scope, settings):
        await websocket.close(code=1008, reason="Origin not allowed")
        return
    try:
        session_id = int(sessionId)
    except ValueError:
        await websocket.close(code=1008, reason="Invalid session")
        return
    runtime: VoiceWebSocketRuntime | None = getattr(
        websocket.app.state,
        "voice_websocket_runtime",
        None,
    )
    if runtime is None:
        await websocket.close(code=1013, reason="Voice service unavailable")
        return
    actor = current_actor(websocket)
    scoped_service = build_service(
        websocket.app.state.infrastructure,
        settings,
        websocket.app.state.metrics,
        actor.user_id,
    )
    if await scoped_service.get_session(session_id) is None:
        await websocket.close(code=1008, reason="Voice session not found")
        return
    session = await runtime.validate_session(session_id)
    if session is None:
        await websocket.close(code=1008, reason="Voice session is not in progress")
        return
    await websocket.accept()
    await runtime.serve(websocket, session)
