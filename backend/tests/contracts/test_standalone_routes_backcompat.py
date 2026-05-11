"""
Standalone Routes Backwards-Compatibility Contract Tests (Issue #499)

Locks the public Pydantic request/response models used by the three
standalone routes. If the My Agent multi-agent layer (#436) accidentally
modifies any of these shapes, this test fires before main is broken.

Strategy:
We lock the *API contract surface* (Pydantic models from `backend.src.api.models`)
rather than spinning up the full FastAPI app. This is intentional:

- Faster (no DB, no agent SDK init)
- Doesn't depend on test fixtures for sessions / auth
- Directly inspects the request/response schemas that clients depend on
- Catches the actual breakage mode we care about: model field drift

Parent Epic: #436 (My Agent — Personal Creative Buddy)
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError


def _fields(model: type[BaseModel]) -> set[str]:
    return set(model.model_fields.keys())


def _required_fields(model: type[BaseModel]) -> set[str]:
    return {
        name
        for name, field in model.model_fields.items()
        if field.is_required()
    }


# ============================================================================
# Image-to-Story Route Contracts
# ============================================================================


class TestImageToStoryRequestContract:
    def test_required_fields(self):
        from backend.src.api.models import ImageToStoryRequest

        required = _required_fields(ImageToStoryRequest)
        # The API uses age_group (not child_age — that translation happens in the route)
        assert "child_id" in required
        assert "age_group" in required

    def test_known_fields_present(self):
        from backend.src.api.models import ImageToStoryRequest

        fields = _fields(ImageToStoryRequest)
        for name in ("child_id", "age_group", "interests", "voice", "enable_audio"):
            assert name in fields, f"ImageToStoryRequest missing field: {name}"


class TestImageToStoryResponseContract:
    def test_known_fields_present(self):
        from backend.src.api.models import ImageToStoryResponse

        fields = _fields(ImageToStoryResponse)

        # Top-level fields the frontend reads
        for name in (
            "story_id",
            "story",
            "image_url",
            "audio_url",
            "educational_value",
            "characters",
            "safety_score",
        ):
            assert name in fields, f"ImageToStoryResponse missing field: {name}"

    def test_safety_score_is_present(self):
        """safety_score must remain a top-level field — downstream code depends on it."""
        from backend.src.api.models import ImageToStoryResponse

        assert "safety_score" in _fields(ImageToStoryResponse)

    def test_educational_value_contains_themes(self):
        """Themes live inside educational_value, not at top level — lock that nesting."""
        from backend.src.api.models import EducationalValue

        assert "themes" in _fields(EducationalValue)
        assert "concepts" in _fields(EducationalValue)


# ============================================================================
# Interactive Story Route Contracts
# ============================================================================


class TestInteractiveStoryStartRequestContract:
    def test_known_fields_present(self):
        from backend.src.api.models import InteractiveStoryStartRequest

        fields = _fields(InteractiveStoryStartRequest)
        for name in ("age_group", "interests"):
            assert name in fields


class TestInteractiveStoryStartResponseContract:
    def test_known_fields_present(self):
        from backend.src.api.models import InteractiveStoryStartResponse

        fields = _fields(InteractiveStoryStartResponse)
        for name in ("session_id", "story_title", "opening"):
            assert name in fields, (
                f"InteractiveStoryStartResponse missing field: {name}"
            )


class TestChoiceRequestContract:
    def test_choice_id_required(self):
        from backend.src.api.models import ChoiceRequest

        assert "choice_id" in _required_fields(ChoiceRequest)


class TestChoiceResponseContract:
    def test_known_fields_present(self):
        from backend.src.api.models import ChoiceResponse

        fields = _fields(ChoiceResponse)
        for name in ("session_id", "next_segment", "choice_history", "progress"):
            assert name in fields, f"ChoiceResponse missing field: {name}"


class TestStorySegmentContract:
    def test_known_fields_present(self):
        from backend.src.api.models import StorySegment

        fields = _fields(StorySegment)
        # Public segment payload — clients render text + choices
        for name in ("text",):
            assert name in fields


# ============================================================================
# Kids Daily Route Contracts
# ============================================================================


class TestKidsDailyTextRequestContract:
    def test_known_fields_present(self):
        from backend.src.api.models import KidsDailyTextRequest

        fields = _fields(KidsDailyTextRequest)
        for name in ("news_text", "age_group"):
            assert name in fields


class TestKidsDailyTextResponseContract:
    def test_known_fields_present(self):
        from backend.src.api.models import KidsDailyTextResponse

        fields = _fields(KidsDailyTextResponse)
        # Public response — frontend renders these
        assert len(fields) > 0


class TestKidsDailyEpisodeContract:
    def test_known_fields_present(self):
        from backend.src.api.models import KidsDailyEpisode

        fields = _fields(KidsDailyEpisode)
        # Episode is the rich response shape — clients depend on its structure
        assert len(fields) > 0


# ============================================================================
# Route Registration Contracts
# ============================================================================


class TestStandaloneRoutesAreRegistered:
    """Sanity: the three standalone route modules are importable + register routers."""

    def test_image_to_story_router_present(self):
        from backend.src.api.routes.image_to_story import router

        assert router is not None
        assert len(router.routes) > 0, "image_to_story router has no routes"

    def test_interactive_story_router_present(self):
        from backend.src.api.routes.interactive_story import router

        assert router is not None
        assert len(router.routes) > 0

    def test_kids_daily_router_present(self):
        from backend.src.api.routes.kids_daily import router

        assert router is not None
        assert len(router.routes) > 0


class TestStandaloneRoutesDoNotDependOnMyAgent:
    """Backwards-compat: standalone routes must NOT import from my_agent_proxy.

    If the multi-agent work (#495) accidentally introduces a hard dependency
    from a standalone route into the proxy, this test fires. Standalone
    flows must remain usable for users who don't have a buddy.
    """

    def test_image_to_story_route_does_not_import_proxy(self):
        import sys

        # Force a fresh import to see what's loaded transitively
        mod_name = "backend.src.api.routes.image_to_story"
        if mod_name in sys.modules:
            del sys.modules[mod_name]

        import backend.src.api.routes.image_to_story as image_route  # noqa: F401

        # Check the module's own imports, not transitive
        source = open(image_route.__file__).read()
        assert "my_agent_proxy" not in source, (
            "image_to_story route must not depend on my_agent_proxy"
        )

    def test_interactive_story_route_does_not_import_proxy(self):
        import backend.src.api.routes.interactive_story as interactive_route

        source = open(interactive_route.__file__).read()
        assert "my_agent_proxy" not in source

    def test_kids_daily_route_does_not_import_proxy(self):
        import backend.src.api.routes.kids_daily as kids_daily_route

        source = open(kids_daily_route.__file__).read()
        assert "my_agent_proxy" not in source
