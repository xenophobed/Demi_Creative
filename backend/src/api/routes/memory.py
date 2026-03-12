"""Memory API routes — preferences and characters (#162, #164).

Exposes read/delete endpoints for the memory system so the frontend can
display favorite themes, suggest topics, and show a character gallery.

Parent Epic: #42
"""

import logging
import re
from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import get_current_user
from ...services.database import preference_repo, character_repo
from ...services.user_service import UserData

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
    result = await preference_repo.get_profile_with_metadata(child_id)
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
    """Remove preference profile + ChromaDB vectors for a child (COPPA compliance, #164)."""
    child_id = _validate_child_id(child_id)

    # Delete SQLite profile
    deleted_sqlite = await preference_repo.delete_profile(child_id)

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
        logger.warning("Failed to delete ChromaDB vectors for child %s", child_id, exc_info=True)

    return {
        "child_id": child_id,
        "deleted": True,
        "deleted_records": {
            "preferences": 1 if deleted_sqlite else 0,
            "vectors": deleted_vectors,
        },
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
    characters = await character_repo.get_characters(child_id)
    return {"child_id": child_id, "characters": characters}
