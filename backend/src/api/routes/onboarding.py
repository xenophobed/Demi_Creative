"""
Onboarding API Routes (#440)

POST /api/v1/me/onboarding/complete — gates onboarding completion behind
explicit parent consent and confirms an agent persona has been created
for the active child profile. Part of Epic #436 (My Agent — personalized
buddy persona).

Behaviour:
  1. parent_consent != True       -> 400 PARENT_CONSENT_REQUIRED
  2. agent missing for (user, child_id) -> 412 AGENT_REQUIRED
  3. Idempotent: when users.onboarded_at is already non-null, return
     200 with the existing timestamps unchanged. Same applies to
     parent_consent_at — we never overwrite a prior consent timestamp.
  4. First completion: write both onboarded_at AND parent_consent_at in
     a single UPDATE so they land atomically.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import get_current_user
from ..models import CompleteOnboardingRequest, UserResponse
from ...services.database import agent_repo, user_repo
from ...services.user_service import UserData
from .users import _user_to_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/me/onboarding", tags=["My Agent"])


@router.post(
    "/complete",
    response_model=UserResponse,
    summary="Complete onboarding (parent-consent gate)",
    description=(
        "Mark the current user as onboarded once they have an agent persona "
        "for the active child profile and a parent has granted consent. "
        "Returns 412 if no agent exists yet, 400 if parent_consent is missing. "
        "Idempotent — replaying the same call returns the existing timestamps."
    ),
)
async def complete_onboarding(
    request: CompleteOnboardingRequest,
    user: UserData = Depends(get_current_user),
):
    if not request.parent_consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PARENT_CONSENT_REQUIRED"},
        )

    agent = await agent_repo.get_agent(user.user_id, request.child_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail={"code": "AGENT_REQUIRED"},
        )

    # Idempotent path: if either timestamp is already set, return the
    # current state unchanged. We refetch fresh to capture any
    # concurrent writes (and to pick up onboarding fields if the
    # request authenticator returned a stale UserData).
    fresh = await user_repo.get_by_id(user.user_id)
    if fresh is None:
        # Defensive — should not happen if get_current_user succeeded.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "USER_LOOKUP_FAILED"},
        )

    if fresh.onboarded_at is None or fresh.parent_consent_at is None:
        now_iso = datetime.now().isoformat()
        # update_onboarding_fields builds a single UPDATE statement, so
        # passing both timestamps writes them atomically.
        await user_repo.update_onboarding_fields(
            user_id=user.user_id,
            onboarded_at=fresh.onboarded_at or now_iso,
            parent_consent_at=fresh.parent_consent_at or now_iso,
        )
        fresh = await user_repo.get_by_id(user.user_id)

    return _user_to_response(fresh, has_agent=True)
