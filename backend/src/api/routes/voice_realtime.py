"""
Talk to Buddy — Realtime Voice routes (#611, epic #605, PRD §3.16).

This is the foundation PR: REST + WS contract are wired but the bodies
return ``501 Not Implemented`` / a documented ``error`` envelope. The
Pydantic models in ``backend/src/api/models.py`` are the authoritative
contract that the frontend (#607.x) codes against; sub-stories
#606.2-#606.5 fill in the real bodies.

Lives in its own module to avoid collision with ``voice.py`` (cloned-voice
TTS, epic #45, story #150).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, status
from fastapi.websockets import WebSocketDisconnect

from ..deps import get_current_user
from ..models import VoiceSessionStartRequest, VoiceSessionStartResponse
from ...services.user_service import UserData

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/me/agent/voice",
    tags=["My Agent — Realtime Voice"],
)


NOT_IMPLEMENTED_DETAIL = {
    "code": "VOICE_REALTIME_NOT_IMPLEMENTED",
    "message": (
        "Talk-to-Buddy realtime voice is not yet wired. Foundation PR #611 "
        "ships the contract only; broker lands in sub-story #606.5."
    ),
}

# Sent over the WS as a JSON-encoded VoiceWSErrorEvent before closing.
NOT_IMPLEMENTED_WS_ENVELOPE = {
    "type": "error",
    "code": "not_implemented",
    "message": "Voice broker not yet wired (#606.5).",
}

WS_CLOSE_NOT_IMPLEMENTED = 1011  # 1011 = "internal error" — best fit for "stub"


@router.post(
    "/session",
    response_model=VoiceSessionStartResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Mint an ephemeral token + WS URL for a Talk-to-Buddy session",
    description=(
        "Validates consent + quota, mints a single-use ephemeral token, "
        "and returns the WebSocket URL to open. Foundation PR returns 501."
    ),
)
async def start_voice_session(
    request: VoiceSessionStartRequest,
    user: UserData = Depends(get_current_user),
):
    # Auth dependency runs first — unauthenticated requests get 401 from
    # `get_current_user` before ever reaching this handler. Once they do
    # reach here we surface a clean 501 with the documented detail shape
    # so the frontend stub-fetch can render a friendly placeholder.
    logger.info(
        "Voice session requested for user=%s child=%s (foundation stub)",
        user.user_id,
        request.child_id,
    )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=NOT_IMPLEMENTED_DETAIL,
    )


@router.websocket("/stream")
async def stream_voice_session(websocket: WebSocket) -> None:
    """WS broker stub.

    Accepts the connection so the browser sees a clean handshake (not a
    network error), emits one documented ``error`` envelope, and closes
    with code ``1011``. Sub-story #606.5 replaces this with the real
    full-duplex broker.
    """
    await websocket.accept()
    try:
        await websocket.send_json(NOT_IMPLEMENTED_WS_ENVELOPE)
    except WebSocketDisconnect:
        return
    finally:
        try:
            await websocket.close(code=WS_CLOSE_NOT_IMPLEMENTED)
        except Exception:
            # Already-closed sockets are fine — nothing to clean up.
            pass
