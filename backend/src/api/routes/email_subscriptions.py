"""Public email subscription routes for Kids Daily previews."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from ..models import (
    KidsDailyEmailSubscriptionRequest,
    KidsDailyEmailSubscriptionResponse,
)
from ...services.database import db_manager


router = APIRouter(
    prefix="/api/v1/email-subscriptions",
    tags=["Email Subscriptions"],
)


@router.post(
    "/kids-daily",
    response_model=KidsDailyEmailSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe an email to Kids Daily previews",
)
async def subscribe_kids_daily_email(
    request: KidsDailyEmailSubscriptionRequest,
) -> KidsDailyEmailSubscriptionResponse:
    now = datetime.utcnow().isoformat()

    try:
        await db_manager.execute(
            """
            INSERT INTO kids_daily_email_subscriptions
                (email, source, subscribed_at, updated_at, is_active)
            VALUES (?, 'homepage', ?, ?, 1)
            ON CONFLICT(email) DO UPDATE SET
                updated_at = excluded.updated_at,
                is_active = 1
            """,
            (request.email, now, now),
        )
        await db_manager.commit()
        row = await db_manager.fetchone(
            """
            SELECT email, subscribed_at
            FROM kids_daily_email_subscriptions
            WHERE email = ?
            """,
            (request.email,),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to subscribe email right now",
        ) from exc

    if not row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to subscribe email right now",
        )

    return KidsDailyEmailSubscriptionResponse(
        email=row["email"],
        subscribed_at=row["subscribed_at"],
        message="subscribed",
    )
