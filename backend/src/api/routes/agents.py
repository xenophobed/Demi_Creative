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
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..deps import get_current_user
from ..models import AgentResponse, UpsertAgentRequest
from ...mcp_servers import check_content_safety
from ...services.agent_constants import (
    AVATAR_IDS,
    CURATED_TITLES_SET,
    MAX_AGENT_NAME_LENGTH,
    MAX_AGENT_TITLE_LENGTH,
)
from ...services.database import agent_repo, user_repo
from ...services.user_service import UserData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/me/agent", tags=["My Agent"])


# Default age the safety check evaluates agent text against. Agent persona
# text is shown to all child age groups, so we use the youngest tier
# (3-5 -> 4) to apply the strictest filter.
_AGENT_SAFETY_TARGET_AGE = 4
_SAFETY_THRESHOLD = 0.85


class _SafetyUnavailableError(RuntimeError):
    """Raised when the safety MCP cannot be reached. Triggers fail-closed."""


async def _run_safety_check(text: str) -> float:
    """
    Run check_content_safety against agent text.

    Returns the safety score (0.0..1.0). Raises _SafetyUnavailableError if
    the MCP server is unreachable or returned an error envelope so the
    caller can fail closed (HTTP 503) — we never silently let unchecked
    text through.
    """
    try:
        result = await check_content_safety({
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
        created_at=datetime.fromisoformat(agent.created_at),
        updated_at=datetime.fromisoformat(agent.updated_at),
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

    # 3. Persist via repository (insert or update on (user_id, child_id)).
    agent = await agent_repo.upsert_agent(
        user_id=user.user_id,
        child_id=request.child_id,
        agent_name=request.agent_name,
        agent_avatar_id=request.agent_avatar_id,
        agent_title=request.agent_title,
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
