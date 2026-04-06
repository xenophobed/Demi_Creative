"""Memory API routes — preferences and characters (#162, #164).

Exposes read/delete endpoints for the memory system so the frontend can
display favorite themes, suggest topics, and show a character gallery.

Parent Epic: #42
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...services.database import character_repo, preference_repo, story_repo
from ...services.theme_recommender import theme_recommender
from ...services.user_service import UserData
from ..deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/memory",
    tags=["Memory"],
)


def _validate_child_id(child_id: str) -> str:
    """Validate child_id format — alphanumeric, underscore, hyphen, 1-100 chars."""
    if not re.match(r"^[a-zA-Z0-9_-]{1,100}$", child_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid child_id format",
        )
    return child_id


@router.get(
    "/preferences/{child_id}",
    summary="Get child preference profile",
)
async def get_preferences(
    child_id: str,
    user: UserData = Depends(get_current_user),
):
    """Return the normalized preference profile with data timestamps (#164)."""
    child_id = _validate_child_id(child_id)
    result = await preference_repo.get_profile_with_metadata(
        child_id, user_id=user.user_id
    )
    return {
        "child_id": child_id,
        "profile": result["profile"],
        "data_collected_since": result["data_collected_since"],
        "last_updated_at": result["last_updated_at"],
    }


@router.delete(
    "/preferences/{child_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete child preference data",
)
async def delete_preferences(
    child_id: str,
    user: UserData = Depends(get_current_user),
):
    """Remove preference profile + characters + ChromaDB vectors for a child."""
    child_id = _validate_child_id(child_id)

    # Delete SQLite profile
    deleted_sqlite = await preference_repo.delete_profile(
        child_id, user_id=user.user_id
    )

    # Delete all character rows for this child
    deleted_characters = await character_repo.delete_characters_for_child(
        user.user_id, child_id
    )

    # Delete ChromaDB vectors for this child
    deleted_vectors = 0
    try:
        import anyio

        from ...mcp_servers.vector_search_server import get_or_create_collection

        collection = await anyio.to_thread.run_sync(get_or_create_collection)
        # Get all document IDs for this child
        results = await anyio.to_thread.run_sync(
            lambda: collection.get(where={"child_id": child_id})
        )
        if results and results.get("ids"):
            doc_ids = results["ids"]
            deleted_vectors = len(doc_ids)
            await anyio.to_thread.run_sync(lambda: collection.delete(ids=doc_ids))
    except Exception:
        logger.warning(
            "Failed to delete ChromaDB vectors for child %s", child_id, exc_info=True
        )

    return {
        "child_id": child_id,
        "deleted": True,
        "deleted_records": {
            "preferences": 1 if deleted_sqlite else 0,
            "characters": deleted_characters,
            "vectors": deleted_vectors,
        },
    }


@router.delete(
    "/preferences/{child_id}/item",
    status_code=status.HTTP_200_OK,
    summary="Delete one preference label",
)
async def delete_preference_item(
    child_id: str,
    category: str = Query(..., description="One of: themes, interests, concepts"),
    label: str = Query(
        ..., min_length=1, max_length=100, description="Label to remove"
    ),
    user: UserData = Depends(get_current_user),
):
    """Delete one preference label from themes/interests/concepts."""
    child_id = _validate_child_id(child_id)
    bucket = category.strip().lower()
    if bucket not in {"themes", "interests", "concepts"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid category. Use themes, interests, or concepts.",
        )
    token = label.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label cannot be empty.",
        )

    deleted = await preference_repo.delete_preference_label(
        child_id,
        bucket,
        token,
        user_id=user.user_id,
    )
    return {
        "child_id": child_id,
        "category": bucket,
        "label": token,
        "deleted": deleted,
    }


@router.get(
    "/characters/{child_id}",
    summary="Get child's character gallery",
)
async def get_characters(
    child_id: str,
    user: UserData = Depends(get_current_user),
):
    """Return all characters for a child, sorted by appearance count."""
    child_id = _validate_child_id(child_id)
    characters = await character_repo.get_characters(user.user_id, child_id)
    return {"child_id": child_id, "characters": characters}


@router.delete(
    "/characters/{child_id}/item",
    status_code=status.HTTP_200_OK,
    summary="Delete one character from memory",
)
async def delete_character_item(
    child_id: str,
    name: str = Query(..., min_length=1, max_length=100, description="Character name"),
    user: UserData = Depends(get_current_user),
):
    """Delete one character by exact name for a child."""
    child_id = _validate_child_id(child_id)
    token = name.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Character name cannot be empty.",
        )

    deleted = await character_repo.delete_character(user.user_id, child_id, token)
    return {
        "child_id": child_id,
        "name": token,
        "deleted": deleted,
    }


@router.get(
    "/recommendations/{child_id}",
    summary="Get personalised theme recommendations",
)
async def get_recommendations(
    child_id: str,
    limit: int = 5,
    user: UserData = Depends(get_current_user),
):
    """Return theme suggestions based on the child's preference history (#292)."""
    child_id = _validate_child_id(child_id)
    if limit < 1:
        limit = 1
    elif limit > 20:
        limit = 20
    recommendations = await theme_recommender.get_recommendations(
        user.user_id,
        child_id,
        limit=limit,
    )
    return {"child_id": child_id, "recommendations": recommendations}


@router.get(
    "/child-id",
    summary="Get user's primary child_id",
)
async def get_child_id(
    user: UserData = Depends(get_current_user),
):
    """Return the best available child_id for this user.

    Priority:
    1) stories (most stories),
    2) characters (highest appearances),
    3) topic subscriptions (most recent),
    4) preferences composite key (most recently updated).
    """
    # 1) Most-used child in stories
    row = await story_repo._db.fetchone(
        """
        SELECT child_id
        FROM stories
        WHERE user_id = ?
        GROUP BY child_id
        ORDER BY COUNT(*) DESC, MAX(created_at) DESC
        LIMIT 1
        """,
        (user.user_id,),
    )
    if row and row.get("child_id"):
        return {"child_id": row["child_id"]}

    # 2) Most-used child in character memory
    row = await character_repo._db.fetchone(
        """
        SELECT child_id
        FROM characters
        WHERE user_id = ?
        GROUP BY child_id
        ORDER BY SUM(appearance_count) DESC, MAX(last_seen_at) DESC
        LIMIT 1
        """,
        (user.user_id,),
    )
    if row and row.get("child_id"):
        return {"child_id": row["child_id"]}

    # 3) Most recent subscribed child
    row = await story_repo._db.fetchone(
        """
        SELECT child_id
        FROM topic_subscriptions
        WHERE user_id = ?
        GROUP BY child_id
        ORDER BY MAX(subscribed_at) DESC
        LIMIT 1
        """,
        (user.user_id,),
    )
    if row and row.get("child_id"):
        return {"child_id": row["child_id"]}

    # 4) Most recent preference profile key (stored as "{user_id}:{child_id}")
    row = await preference_repo._db.fetchone(
        """
        SELECT child_id
        FROM child_preferences
        WHERE child_id LIKE ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (f"{user.user_id}:%",),
    )
    if row and row.get("child_id"):
        token = row["child_id"]
        if ":" in token:
            token = token.split(":", 1)[1]
        return {"child_id": token}

    return {"child_id": None}
