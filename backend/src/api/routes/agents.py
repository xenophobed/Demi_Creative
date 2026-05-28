"""
Agent API Routes (#439)

Endpoints to fetch and upsert the personalized agent persona for the
current user. Part of Epic #436 (My Agent — personalized buddy persona).

Validation pipeline for PUT /me/agent:
  1. Pydantic length checks (agent_name, agent_title <= 32, child_id present).
  2. agent_avatar_id must be in the AVATAR_IDS whitelist.
  3. agent_title: curated entries skip the safety check (already approved);
     free-text entries go through check_content_safety.
  4. agent_name always goes through check_content_safety.
  5. If the safety MCP raises or returns an error envelope, fail closed
     with HTTP 503 SAFETY_UNAVAILABLE — never let unchecked content
     through.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from ..deps import get_current_user, require_owned_child_profile
from ..models import (
    AgentChatMessageItem,
    AgentChatMessagesResponse,
    AgentChatRequest,
    AgentChatSessionListResponse,
    AgentChatSessionSummary,
    AgentResponse,
    CreateAgentChatSessionRequest,
    UpdateAgentChatSessionRequest,
    UpsertAgentRequest,
)
from ...agents.my_agent_proxy import stream_my_agent_chat
from ...mcp_servers import check_content_safety
from ...services.agent_constants import (
    AVATAR_IDS,
    CURATED_TITLES_SET,
    MAX_AGENT_NAME_LENGTH,
    MAX_AGENT_TITLE_LENGTH,
)
from ...services.database import agent_chat_repo, agent_repo, user_repo
from ...services.user_service import UserData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/me/agent", tags=["My Agent"])


# Default age the safety check evaluates agent text against. Agent persona
# text is shown to all child age groups, so we use the youngest tier
# (3-5 -> 4) to apply the strictest filter.
_AGENT_SAFETY_TARGET_AGE = 4
_SAFETY_THRESHOLD = 0.85
_ALLOWED_TONES = {
    "warm_curious",
    "funny_playful",
    "calm_gentle",
    "adventurous",
    "teacherly",
}
_ALLOWED_INTERACTION_STYLES = {
    "guided_playful",
    "question_first",
    "storyteller",
    "coach",
}
_ALLOWED_SKILLS = {
    "image_story",
    "interactive_story",
    "kids_daily",
    "audio_narration",
}


class _SafetyUnavailableError(RuntimeError):
    """Raised when the safety MCP cannot be reached. Triggers fail-closed."""


async def _run_safety_check(text: str) -> float:
    """
    Run check_content_safety against agent text.

    Returns the safety score (0.0..1.0). Raises _SafetyUnavailableError if
    the MCP server is unreachable or returned an error envelope so the
    caller can fail closed (HTTP 503) — we never silently let unchecked
    text through.

    Note: ``check_content_safety`` is decorated with the SDK's ``@tool``,
    which wraps it in an ``SdkMcpTool`` registration object that is NOT
    itself callable. The raw async handler lives at ``.handler``. Without
    this we'd get ``TypeError: 'SdkMcpTool' object is not callable``,
    which the outer ``except Exception`` catches and surfaces to the
    user as ``Our safety checker is taking a break.`` (HTTP 503).
    """
    try:
        result = await check_content_safety.handler({
            "content_text": text,
            "content_type": "agent_persona",
            "target_age": _AGENT_SAFETY_TARGET_AGE,
        })
    except Exception as exc:  # noqa: BLE001 — fail closed on any error
        logger.warning(
            "Safety MCP unavailable for agent text, failing closed",
            exc_info=True,
        )
        raise _SafetyUnavailableError(str(exc)) from exc

    try:
        data = json.loads(result["content"][0]["text"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning("Safety MCP returned malformed payload, failing closed")
        raise _SafetyUnavailableError("malformed safety payload") from exc

    if "error" in data:
        logger.warning(
            "Safety MCP returned error envelope, failing closed: %s",
            data["error"],
        )
        raise _SafetyUnavailableError(str(data["error"]))

    score = data.get("safety_score")
    if score is None:
        # Missing score field -> cannot verify safety -> fail closed.
        raise _SafetyUnavailableError("safety_score missing from response")

    return float(score)


def _to_response(agent) -> AgentResponse:
    """Convert AgentData to AgentResponse (parses ISO timestamps)."""
    return AgentResponse(
        agent_id=agent.agent_id,
        user_id=agent.user_id,
        child_id=agent.child_id,
        agent_name=agent.agent_name,
        agent_avatar_id=agent.agent_avatar_id,
        agent_title=agent.agent_title,
        tone=agent.tone,
        interaction_style=agent.interaction_style,
        enabled_skills=agent.enabled_skills or [],
        favorite_topics=agent.favorite_topics or [],
        learning_goals=agent.learning_goals or [],
        custom_instructions=agent.custom_instructions or "",
        created_at=datetime.fromisoformat(agent.created_at),
        updated_at=datetime.fromisoformat(agent.updated_at),
    )


def _clean_list(values: list[str], *, max_items: int = 8, max_len: int = 40) -> list[str]:
    cleaned: list[str] = []
    for value in values or []:
        item = str(value).strip()
        if not item:
            continue
        cleaned.append(item[:max_len])
        if len(cleaned) >= max_items:
            break
    return cleaned


async def _safety_check_optional_text(text: str, code_prefix: str) -> None:
    cleaned = text.strip()
    if not cleaned:
        return
    try:
        score = await _run_safety_check(cleaned)
    except _SafetyUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "SAFETY_UNAVAILABLE"},
        )
    if score < _SAFETY_THRESHOLD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": f"UNSAFE_{code_prefix}",
                "reason": "This buddy setting did not pass content safety check",
                "score": score,
            },
        )


@router.get(
    "",
    response_model=AgentResponse,
    summary="Get current user's agent persona",
    description="Return the agent bound to (current_user, child_id).",
)
async def get_my_agent(
    child_id: str = Query(..., min_length=1, description="Child profile ID"),
    user: UserData = Depends(get_current_user),
):
    """Look up the agent for (user_id, child_id). 404 if no row exists."""
    await require_owned_child_profile(user, child_id)
    agent = await agent_repo.get_agent(user.user_id, child_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "AGENT_NOT_FOUND"},
        )
    return _to_response(agent)


@router.put(
    "",
    response_model=AgentResponse,
    summary="Create or update current user's agent persona",
    description=(
        "Upsert the agent persona bound to (current_user, child_id). "
        "Validates avatar against the whitelist and runs the safety check on "
        "the agent name (and on titles outside the curated list)."
    ),
)
async def upsert_my_agent(
    request: UpsertAgentRequest,
    user: UserData = Depends(get_current_user),
):
    """
    Upsert flow:
      1. Whitelist avatar (cheap deterministic check).
      2. Safety-check agent_name and free-text agent_title.
      3. Upsert to user_agents.
      4. Return AgentResponse.
    """
    await require_owned_child_profile(user, request.child_id)

    # 1. Avatar whitelist
    if request.agent_avatar_id not in AVATAR_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_AVATAR"},
        )

    # 2a. Title validation: skip safety check if curated.
    title = request.agent_title
    if title not in CURATED_TITLES_SET:
        # Free-text path. Pydantic already enforced 1..MAX_AGENT_TITLE_LENGTH,
        # but we keep this guard explicit so the contract is local to this
        # route even if the model changes.
        if not (1 <= len(title) <= MAX_AGENT_TITLE_LENGTH):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_AGENT_TITLE"},
            )
        try:
            title_score = await _run_safety_check(title)
        except _SafetyUnavailableError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "SAFETY_UNAVAILABLE"},
            )
        if title_score < _SAFETY_THRESHOLD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "UNSAFE_AGENT_TITLE",
                    "reason": "Title did not pass content safety check",
                    "score": title_score,
                },
            )

    # 2b. Name always goes through safety check.
    if not (1 <= len(request.agent_name) <= MAX_AGENT_NAME_LENGTH):
        # Belt-and-suspenders — Pydantic already enforces this.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_AGENT_NAME"},
        )
    try:
        name_score = await _run_safety_check(request.agent_name)
    except _SafetyUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "SAFETY_UNAVAILABLE"},
        )
    if name_score < _SAFETY_THRESHOLD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "UNSAFE_AGENT_NAME",
                "reason": "Name did not pass content safety check",
                "score": name_score,
            },
        )

    tone = request.tone if request.tone in _ALLOWED_TONES else "warm_curious"
    interaction_style = (
        request.interaction_style
        if request.interaction_style in _ALLOWED_INTERACTION_STYLES
        else "guided_playful"
    )
    enabled_skills = [
        skill for skill in (request.enabled_skills or []) if skill in _ALLOWED_SKILLS
    ]
    if not enabled_skills:
        enabled_skills = [
            "image_story",
            "interactive_story",
            "kids_daily",
            "audio_narration",
        ]
    favorite_topics = _clean_list(request.favorite_topics)
    learning_goals = _clean_list(request.learning_goals)
    custom_instructions = (request.custom_instructions or "").strip()[:500]

    await _safety_check_optional_text(custom_instructions, "CUSTOM_INSTRUCTIONS")
    await _safety_check_optional_text(" ".join(favorite_topics), "FAVORITE_TOPICS")
    await _safety_check_optional_text(" ".join(learning_goals), "LEARNING_GOALS")

    # 3. Persist via repository (insert or update on (user_id, child_id)).
    agent = await agent_repo.upsert_agent(
        user_id=user.user_id,
        child_id=request.child_id,
        agent_name=request.agent_name,
        agent_avatar_id=request.agent_avatar_id,
        agent_title=request.agent_title,
        tone=tone,
        interaction_style=interaction_style,
        enabled_skills=enabled_skills,
        favorite_topics=favorite_topics,
        learning_goals=learning_goals,
        custom_instructions=custom_instructions,
    )

    # 4. Persist default_child_id on first agent creation (#455). Set-once
    # semantics — if the user already has a default_child_id, keep it.
    # This anchors the buddy identity server-side so a fresh browser/device
    # restores the same child profile after login.
    if user.default_child_id is None:
        await user_repo.update_onboarding_fields(
            user_id=user.user_id,
            default_child_id=request.child_id,
        )

    return _to_response(agent)


async def _parse_chat_request(request: Request) -> tuple[AgentChatRequest, str | None]:
    content_type = request.headers.get("content-type", "")
    image_path: str | None = None
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        payload = AgentChatRequest(
            child_id=str(form.get("child_id") or ""),
            message=str(form.get("message") or ""),
            session_id=str(form.get("session_id") or "") or None,
            age_group=str(form.get("age_group") or "") or None,
            interests=[
                str(v).strip()
                for v in str(form.get("interests") or "").split(",")
                if str(v).strip()
            ],
        )
        upload = form.get("image")
        if upload is not None and hasattr(upload, "read"):
            suffix = Path(getattr(upload, "filename", "") or "upload.png").suffix or ".png"
            data = await upload.read()
            tmp = NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(data)
            tmp.close()
            image_path = tmp.name
        return payload, image_path

    data = await request.json()
    return AgentChatRequest(**data), None


@router.post(
    "/chat/stream",
    summary="Chat with the current user's My Agent buddy",
    description="Streams buddy chat and specialist tool results as SSE.",
)
async def chat_with_my_agent_stream(
    request: Request,
    user: UserData = Depends(get_current_user),
):
    try:
        payload, image_path = await _parse_chat_request(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_AGENT_CHAT_REQUEST", "reason": str(exc)},
        )

    await require_owned_child_profile(user, payload.child_id)

    async def _events():
        try:
            async for event in stream_my_agent_chat(
                user_id=user.user_id,
                child_id=payload.child_id,
                message=payload.message,
                session_id=payload.session_id,
                image_path=image_path,
                age_group=payload.age_group,
                interests=payload.interests,
            ):
                yield event
        finally:
            if image_path:
                try:
                    os.unlink(image_path)
                except OSError:
                    pass

    return StreamingResponse(_events(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Multi-topic chat sessions (#565 §3.11.8) — read endpoints (#567)
# ---------------------------------------------------------------------------


def _session_to_summary(session) -> AgentChatSessionSummary:
    return AgentChatSessionSummary(
        session_id=session.session_id,
        child_id=session.child_id,
        title=session.title,
        last_message_preview=session.last_message_preview,
        archived_at=session.archived_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get(
    "/sessions",
    response_model=AgentChatSessionListResponse,
    summary="List the current user's buddy chat sessions",
    description="Returns sessions for (current_user, optional child_id), most-recently-updated first.",
)
async def list_agent_sessions(
    child_id: str | None = Query(None, description="Optional child profile filter"),
    include_archived: bool = Query(False, description="Include archived sessions"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: UserData = Depends(get_current_user),
):
    """List chat sessions scoped to the calling user (cross-user isolation #288)."""
    if child_id:
        await require_owned_child_profile(user, child_id)
    sessions = await agent_chat_repo.list_sessions_for_user(
        user.user_id,
        child_id=child_id,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return AgentChatSessionListResponse(
        sessions=[_session_to_summary(s) for s in sessions]
    )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=AgentChatMessagesResponse,
    summary="Get a buddy chat session's message history",
    description="Returns chronological history for a session the caller owns; 404 otherwise.",
)
async def get_agent_session_messages(
    session_id: str,
    limit: int = Query(200, ge=1, le=500),
    before_created_at: str | None = Query(None, description="Cursor: only messages strictly before this ISO timestamp"),
    user: UserData = Depends(get_current_user),
):
    """Fetch one session's history. A session not owned by the caller 404s —
    we never leak existence, matching the agent_repo.get_session contract."""
    owner = await agent_chat_repo.get_session(session_id, user_id=user.user_id)
    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND"},
        )
    messages = await agent_chat_repo.list_messages(
        session_id,
        user_id=user.user_id,
        limit=limit,
        before_created_at=before_created_at,
    )
    return AgentChatMessagesResponse(
        session_id=session_id,
        messages=[
            AgentChatMessageItem(
                message_id=m.message_id,
                role=m.role,
                text=m.text,
                result_metadata=m.result_metadata,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


# ---------------------------------------------------------------------------
# Multi-topic chat sessions — write endpoints (#568)
# ---------------------------------------------------------------------------


@router.post(
    "/sessions",
    response_model=AgentChatSessionSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create a fresh buddy chat session",
    description="Starts an empty session for (current_user, child_id) before the first message.",
)
async def create_agent_session(
    request: CreateAgentChatSessionRequest,
    user: UserData = Depends(get_current_user),
):
    """Create an empty session. The optional title is safety-checked like
    a rename so a child cannot seed an unsafe title at creation time."""
    await require_owned_child_profile(user, request.child_id)

    session = await agent_chat_repo.get_or_create_session(
        user_id=user.user_id, child_id=request.child_id
    )
    title = (request.title or "").strip()
    if title:
        await _guard_session_title(title)
        await agent_chat_repo.rename_session(
            session.session_id, user_id=user.user_id, title=title
        )
        session = await agent_chat_repo.get_session(
            session.session_id, user_id=user.user_id
        )
    return _session_to_summary(session)


@router.patch(
    "/sessions/{session_id}",
    response_model=AgentChatSessionSummary,
    summary="Rename and/or archive a buddy chat session",
    description="Renames (safety-checked) and/or archives a session the caller owns.",
)
async def update_agent_session(
    session_id: str,
    request: UpdateAgentChatSessionRequest,
    user: UserData = Depends(get_current_user),
):
    """Rename / archive. A foreign or unknown session 404s before any
    mutation, so a cross-tenant request can never touch another's row."""
    owner = await agent_chat_repo.get_session(session_id, user_id=user.user_id)
    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND"},
        )

    if request.title is not None:
        title = request.title.strip()
        if not title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_SESSION_TITLE"},
            )
        await _guard_session_title(title)
        await agent_chat_repo.rename_session(
            session_id, user_id=user.user_id, title=title
        )

    if request.archived is not None:
        await agent_chat_repo.archive_session(
            session_id, user_id=user.user_id, archived=request.archived
        )

    updated = await agent_chat_repo.get_session(session_id, user_id=user.user_id)
    return _session_to_summary(updated)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a buddy chat session",
    description="Hard-deletes a session the caller owns; messages cascade via FK.",
)
async def delete_agent_session(
    session_id: str,
    user: UserData = Depends(get_current_user),
):
    """Hard delete. A foreign or unknown session 404s; otherwise the row
    and its messages are removed via the ON DELETE CASCADE FK."""
    deleted = await agent_chat_repo.delete_session(session_id, user_id=user.user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND"},
        )
    return None


async def _guard_session_title(title: str) -> None:
    """Run the shared safety check on a user-supplied session title.

    Reuses the agent-persona safety bar (0.85) so a session title can't
    sneak content the persona name couldn't. Fails closed on MCP outage.
    """
    try:
        score = await _run_safety_check(title)
    except _SafetyUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "SAFETY_UNAVAILABLE"},
        )
    if score < _SAFETY_THRESHOLD:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "UNSAFE_SESSION_TITLE",
                "reason": "Title did not pass content safety check",
                "score": score,
            },
        )
