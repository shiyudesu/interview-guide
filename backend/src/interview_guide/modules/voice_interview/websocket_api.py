from __future__ import annotations

from fastapi import APIRouter, WebSocket

from interview_guide.modules.voice_interview.websocket import VoiceWebSocketRuntime

router = APIRouter()


@router.websocket("/ws/voice-interview/{sessionId}")
async def voice_interview_websocket(
    websocket: WebSocket,
    sessionId: str,
) -> None:
    settings = websocket.app.state.settings
    origin = websocket.headers.get("origin")
    if origin is not None and origin not in settings.allowed_origins:
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
    session = await runtime.validate_session(session_id)
    if session is None:
        await websocket.close(code=1008, reason="Voice session is not in progress")
        return
    await websocket.accept()
    await runtime.serve(websocket, session)
