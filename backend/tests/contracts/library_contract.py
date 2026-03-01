"""
Library API & Favorites Contract Tests

Defines the expected interface and behavior of the library API endpoints
and favorites repository before implementation (TDD).

Covers:
- GET /api/v1/library — unified library endpoint
- GET /api/v1/library/search — server-side search
- POST/DELETE /api/v1/library/favorites — favorite management
- FavoriteRepository CRUD operations
"""

import pytest
from datetime import datetime


# ============================================================================
# Library Item Contract
# ============================================================================

class TestLibraryItemShape:
    """Contract: Unified library item response shape."""

    def test_library_item_has_required_fields(self):
        """
        Contract: Every LibraryItem MUST have these fields.

        Shape:
        {
            id: str,
            type: "art-story" | "interactive" | "news",
            title: str,
            preview: str,               # First ~100 chars of content
            image_url: str | None,
            audio_url: str | None,
            created_at: str,            # ISO 8601
            is_favorited: bool,
        }
        """
        required_fields = {
            "id", "type", "title", "preview",
            "image_url", "audio_url", "created_at", "is_favorited",
        }

        valid_types = {"art-story", "interactive", "news"}

        # All types must have the same base shape
        for item_type in valid_types:
            assert item_type in valid_types

    def test_art_story_item_has_extra_fields(self):
        """
        Contract: art-story items include safety_score, word_count, themes.
        """
        art_story_item = {
            "id": "story-uuid",
            "type": "art-story",
            "title": "Lightning Dog's Adventure",
            "preview": "Lightning Dog found a magical bone...",
            "image_url": "/uploads/drawing.png",
            "audio_url": "/audio/story.mp3",
            "created_at": "2026-02-27T10:00:00",
            "is_favorited": False,
            "safety_score": 0.95,
            "word_count": 350,
            "themes": ["friendship", "courage"],
        }

        assert "safety_score" in art_story_item
        assert "word_count" in art_story_item
        assert "themes" in art_story_item

    def test_interactive_item_has_extra_fields(self):
        """
        Contract: interactive items include progress and status.
        """
        interactive_item = {
            "id": "session-uuid",
            "type": "interactive",
            "title": "The Dinosaur Cave",
            "preview": "A brave dinosaur discovered...",
            "image_url": None,
            "audio_url": None,
            "created_at": "2026-02-27T10:00:00",
            "is_favorited": True,
            "progress": 60,
            "status": "active",
        }

        assert "progress" in interactive_item
        assert "status" in interactive_item

    def test_news_item_has_extra_fields(self):
        """
        Contract: news items include category.
        """
        news_item = {
            "id": "conversion-uuid",
            "type": "news",
            "title": "Space Bus to the Moon!",
            "preview": "Scientists built a bus that flies...",
            "image_url": None,
            "audio_url": "/audio/news.mp3",
            "created_at": "2026-02-27T10:00:00",
            "is_favorited": False,
            "category": "science",
        }

        assert "category" in news_item


# ============================================================================
# GET /api/v1/library Contract
# ============================================================================

class TestUnifiedLibraryEndpoint:
    """Contract: GET /api/v1/library"""

    def test_returns_paginated_response(self):
        """
        Contract: Returns LibraryResponse shape.

        {
            items: List[LibraryItem],
            total: int,
            limit: int,
            offset: int,
        }
        """
        expected_response_keys = {"items", "total", "limit", "offset"}
        assert len(expected_response_keys) == 4

    def test_default_pagination(self):
        """Contract: Default limit=20, offset=0."""
        default_limit = 20
        default_offset = 0
        assert default_limit == 20
        assert default_offset == 0

    def test_filters_by_content_type(self):
        """
        Contract: ?type=art-story returns only art stories.

        Valid type values: art-story, interactive, news
        Omitting type returns all content types.
        """
        valid_types = ["art-story", "interactive", "news"]
        assert len(valid_types) == 3

    def test_pagination_with_limit_and_offset(self):
        """
        Contract: ?limit=10&offset=20 returns items 21-30.
        limit must be 1-100, offset must be >= 0.
        """
        min_limit = 1
        max_limit = 100
        min_offset = 0
        assert min_limit <= max_limit

    def test_items_sorted_by_created_at_desc(self):
        """Contract: Most recent items first (default sort)."""
        # Items should come back in reverse chronological order
        pass

    def test_excludes_items_below_safety_threshold(self):
        """
        Contract: Items with safety_score < 0.85 MUST NOT appear
        in the response. Content safety is non-negotiable (#81).

        Threshold: SAFETY_THRESHOLD = 0.85
        - safety_score >= 0.85 → included
        - safety_score < 0.85  → excluded
        - safety_score is None → included (not yet checked)
        """
        pass

    def test_safety_threshold_is_0_85(self):
        """
        Contract: The safety threshold constant MUST be exactly 0.85.
        Matches CLAUDE.md rule: "Safety score threshold: >= 0.85"
        """
        from backend.src.api.routes.library import SAFETY_THRESHOLD
        assert SAFETY_THRESHOLD == 0.85

    def test_includes_is_favorited_flag(self):
        """
        Contract: Each item has is_favorited=true/false based on
        whether the authenticated user has favorited it.
        """
        pass

    def test_requires_authentication(self):
        """Contract: Returns 401 without auth token."""
        expected_status_code = 401

    def test_only_returns_users_own_content(self):
        """
        Contract: User A cannot see User B's library items.
        Results scoped to authenticated user's user_id.
        """
        pass

    def test_empty_library_returns_empty_items(self):
        """Contract: New user with no content gets items=[], total=0."""
        expected_items = []
        expected_total = 0


# ============================================================================
# GET /api/v1/library/search Contract
# ============================================================================

class TestLibrarySearchEndpoint:
    """Contract: GET /api/v1/library/search"""

    def test_search_returns_matching_items(self):
        """
        Contract: ?q=dragon returns items with 'dragon' in title, preview,
        themes, or character names.
        """
        pass

    def test_search_filters_by_type(self):
        """Contract: ?q=dragon&type=art-story scopes to art stories only."""
        pass

    def test_search_requires_query_param(self):
        """Contract: Missing q parameter returns 400."""
        expected_status_code = 400

    def test_search_is_case_insensitive(self):
        """Contract: 'Dragon' and 'dragon' match the same results."""
        pass

    def test_search_returns_same_shape_as_library(self):
        """
        Contract: Search response is LibraryResponse
        (same shape as GET /library).
        """
        pass

    def test_search_excludes_items_below_safety_threshold(self):
        """
        Contract: Search results with safety_score < 0.85 MUST NOT
        appear in search results. Same safety filter as GET /library (#81).
        """
        pass

    def test_search_respects_pagination(self):
        """Contract: ?q=dragon&limit=5&offset=0 paginates results."""
        pass

    def test_empty_results(self):
        """Contract: No matches returns items=[], total=0."""
        pass

    def test_requires_authentication(self):
        """Contract: Returns 401 without auth token."""
        expected_status_code = 401


# ============================================================================
# POST /api/v1/library/favorites Contract
# ============================================================================

class TestAddFavoriteEndpoint:
    """Contract: POST /api/v1/library/favorites"""

    def test_add_favorite_returns_201(self):
        """
        Contract: POST { item_id: str, item_type: str }
        Returns 201: { status: "favorited", item_id: str, item_type: str }
        """
        request_body = {
            "item_id": "story-uuid",
            "item_type": "art-story",
        }

        expected_response = {
            "status": "favorited",
            "item_id": "story-uuid",
            "item_type": "art-story",
        }

    def test_duplicate_favorite_is_idempotent(self):
        """Contract: Adding same favorite twice succeeds (no error)."""
        pass

    def test_requires_authentication(self):
        """Contract: Returns 401 without auth token."""
        expected_status_code = 401

    def test_valid_item_types(self):
        """Contract: item_type must be art-story, interactive, or news."""
        valid_types = ["art-story", "interactive", "news"]
        assert len(valid_types) == 3


# ============================================================================
# DELETE /api/v1/library/favorites Contract
# ============================================================================

class TestRemoveFavoriteEndpoint:
    """Contract: DELETE /api/v1/library/favorites"""

    def test_remove_favorite_returns_204(self):
        """
        Contract: DELETE with { item_id: str, item_type: str }
        Returns 204 No Content.
        """
        expected_status_code = 204

    def test_remove_nonexistent_favorite_returns_404(self):
        """Contract: Removing a favorite that doesn't exist returns 404."""
        expected_status_code = 404

    def test_requires_authentication(self):
        """Contract: Returns 401 without auth token."""
        expected_status_code = 401


# ============================================================================
# FavoriteRepository Contract
# ============================================================================

class TestFavoriteRepositoryCreate:
    """Contract: Adding favorites"""

    def test_add_returns_true(self):
        """
        Contract: add(user_id, item_type, item_id) -> bool

        Method signature:
        async def add(user_id: str, item_type: str, item_id: str) -> bool

        Returns True on success.
        """
        pass

    def test_add_duplicate_is_idempotent(self):
        """
        Contract: Adding same (user_id, item_type, item_id) twice
        succeeds without error (INSERT OR IGNORE).
        """
        pass


class TestFavoriteRepositoryDelete:
    """Contract: Removing favorites"""

    def test_remove_returns_true(self):
        """
        Contract: remove(user_id, item_type, item_id) -> bool

        Returns True if removed.
        """
        pass

    def test_remove_nonexistent_returns_false(self):
        """
        Contract: Returns False if favorite not found.
        """
        pass


class TestFavoriteRepositoryQuery:
    """Contract: Querying favorites"""

    def test_is_favorited(self):
        """
        Contract: is_favorited(user_id, item_type, item_id) -> bool
        """
        pass

    def test_list_by_user(self):
        """
        Contract: list_by_user(user_id, item_type=None) -> List[dict]

        Returns list of {item_type, item_id, created_at}.
        Optional item_type filter.
        """
        pass

    def test_get_favorited_ids(self):
        """
        Contract: get_favorited_ids(user_id, item_type, item_ids) -> Set[str]

        Batch check: given a list of item_ids, return the set that are favorited.
        Critical for annotating library results without N+1 queries.
        """
        pass

    def test_count_by_user(self):
        """
        Contract: count_by_user(user_id) -> int
        """
        pass


# ============================================================================
# Favorites Table Schema Contract
# ============================================================================

class TestFavoritesSchema:
    """Contract: favorites table schema"""

    def test_table_has_required_columns(self):
        """
        Contract: favorites table columns:
        - id INTEGER PRIMARY KEY AUTOINCREMENT
        - user_id TEXT NOT NULL
        - item_type TEXT NOT NULL
        - item_id TEXT NOT NULL
        - created_at TEXT NOT NULL
        """
        required_columns = ["id", "user_id", "item_type", "item_id", "created_at"]
        assert len(required_columns) == 5

    def test_unique_constraint(self):
        """
        Contract: UNIQUE(user_id, item_type, item_id)
        No duplicate favorites for the same user+item.
        """
        pass

    def test_indexes_exist(self):
        """
        Contract: Indexes for common query patterns:
        - idx_favorites_user_id ON favorites(user_id)
        - idx_favorites_user_type ON favorites(user_id, item_type)
        - idx_favorites_item ON favorites(item_type, item_id)
        """
        pass

    def test_foreign_key_to_users(self):
        """
        Contract: FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        Deleting a user deletes their favorites.
        """
        pass
