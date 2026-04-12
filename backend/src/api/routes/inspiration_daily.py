"""
Inspiration Daily API routes — daily creative inspiration content.

Serves age-adapted creative project inspiration cards from the seed bank,
with deterministic daily rotation. See PRD §3.10.

Related issues: #405 (epic), #408 (this endpoint), #410 (age adaptation)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

from ..models import AgeGroup, InspirationDailyResponse
from ...services.inspiration_seed_bank import get_daily_seed

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/inspiration-daily",
    tags=["Inspiration Daily"],
)


@router.get(
    "",
    response_model=InspirationDailyResponse,
    summary="Get today's creative inspiration card",
)
async def get_daily_inspiration(
    age_group: Optional[str] = Query(
        default="6-8",
        description="Child's age group for content adaptation",
        pattern=r"^(3-5|6-8|9-12)$",
    ),
) -> InspirationDailyResponse:
    """
    Fetch today's daily creative inspiration card.

    Returns a single InspirationCard with age-adapted summary and creative prompt.
    Content rotates daily from the seed bank. No authentication required so
    unauthenticated users can see a preview.
    """
    card = get_daily_seed()

    if card is None:
        logger.error("No seed bank entries available")
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="No inspiration content available")

    age_key = age_group or "6-8"
    adaptation = card.age_adaptations.get(age_key)

    if adaptation:
        adapted_summary = adaptation.summary
        adapted_prompt = adaptation.creative_prompt
    else:
        adapted_summary = card.summary
        adapted_prompt = card.creative_prompt

    return InspirationDailyResponse(
        card=card,
        age_group=age_key,
        adapted_summary=adapted_summary,
        adapted_prompt=adapted_prompt,
    )
