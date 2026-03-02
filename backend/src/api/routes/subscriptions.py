"""Subscription CRUD routes for Morning Show topics (#94)."""

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import get_current_user
from ..models import (
    NewsCategory,
    SubscriptionListResponse,
    SubscriptionRequest,
    SubscriptionResponse,
    TopicSubscription,
)
from ...services.database import (
    DuplicateSubscriptionError,
    MaxSubscriptionsExceededError,
    subscription_repo,
)
from ...services.user_service import UserData


router = APIRouter(
    prefix="/api/v1/subscriptions",
    tags=["Subscriptions"],
)


@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe to a Morning Show topic",
)
async def subscribe_topic(
    request: SubscriptionRequest,
    user: UserData = Depends(get_current_user),
):
    try:
        created = await subscription_repo.create(
            user_id=user.user_id,
            child_id=request.child_id,
            topic=request.topic.value,
        )
    except DuplicateSubscriptionError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Subscription already exists",
        )
    except MaxSubscriptionsExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return SubscriptionResponse(
        child_id=created["child_id"],
        topic=created["topic"],
        subscribed_at=created["subscribed_at"],
        is_active=created["is_active"],
        message="subscribed",
    )


@router.delete(
    "/{child_id}/{topic}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unsubscribe from a topic",
)
async def unsubscribe_topic(
    child_id: str,
    topic: NewsCategory,
    user: UserData = Depends(get_current_user),
):
    removed = await subscription_repo.deactivate(
        user_id=user.user_id,
        child_id=child_id,
        topic=topic.value,
    )

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )


@router.get(
    "/{child_id}",
    response_model=SubscriptionListResponse,
    summary="List active subscriptions for a child",
)
async def list_subscriptions(
    child_id: str,
    user: UserData = Depends(get_current_user),
):
    rows = await subscription_repo.list_active(user.user_id, child_id)
    items = [
        TopicSubscription(
            child_id=row["child_id"],
            topic=row["topic"],
            subscribed_at=row["subscribed_at"],
            is_active=row["is_active"],
        )
        for row in rows
    ]
    return SubscriptionListResponse(items=items, total=len(items))
