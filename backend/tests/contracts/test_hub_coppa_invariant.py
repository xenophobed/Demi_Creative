"""COPPA Invariant Contract Tests for Content Hub

Locks the privacy guardrail for Content Hub (Epic #437): hub read endpoints
MUST NEVER return any users-table column. The forbidden-key list below
serves as the design specification for the response shape introduced by
story #449.

This file is intentionally skip-guarded by an *import-based* check. Once
#449 lands `src.api.routes.hub`, the import succeeds and the hub-dependent
tests auto-activate without further changes here.

The walker positive-control test runs unconditionally — it guarantees the
generic helper actually fails on a planted violation, so we never get a
false sense of safety from the skipped tests.

Related: #450, parent epic #437, depends on #449.
"""

from __future__ import annotations

import pytest

from tests.contracts._pii_walker import assert_no_pii


# Import-based skip guard. When #449 introduces src.api.routes.hub,
# _HUB_AVAILABLE flips to True and the hub-dependent tests run.
try:
    from src.api.routes import hub  # type: ignore  # noqa: F401

    _HUB_AVAILABLE = True
except Exception:  # pragma: no cover - defensive: any import error => skip
    _HUB_AVAILABLE = False


# ---------------------------------------------------------------------------
# Forbidden lists — the design contract for #449.
#
# Any hub response containing one of these keys (case-insensitively) is a
# COPPA violation. Reuse these constants in #449's own tests so the contract
# stays single-sourced.
# ---------------------------------------------------------------------------
FORBIDDEN_USER_KEYS: frozenset[str] = frozenset(
    {
        "user_id",
        "username",
        "email",
        "display_name",
        "avatar_url",
        "role",
        "membership_tier",
        "referral_code",
        "referred_by",
        "password_hash",
        "parent_consent_at",
        "nickname",
        "onboarded_at",
        "default_child_id",
    }
)

FORBIDDEN_USER_KEY_SUBSTRINGS: frozenset[str] = frozenset()  # reserved for future


# Distinctive canary values planted in seeded user records so we can detect
# value-level leaks (e.g. an email accidentally rendered into a `caption`
# field would still be caught even though the key is innocuous).
_CANARY_EMAIL = "pii.canary@test.invalid"
_CANARY_DISPLAY_NAME = "USER_PII_DISPLAY_NAME_xZ8q"
_CANARY_USERNAME = "user_pii_canary_username_xZ8q"


# ---------------------------------------------------------------------------
# Positive control — runs unconditionally.
# ---------------------------------------------------------------------------
def test_walker_catches_planted_pii_in_fixture() -> None:
    """Positive control: the walker must fail on a deliberately planted leak.

    This test does NOT hit the hub — it validates the helper itself, so it
    runs regardless of whether #449 has shipped. Without this control, the
    skipped tests would give false confidence.
    """
    poisoned_payload = {
        "posts": [
            {
                "post_id": "p1",
                "author": {"user_id": "uX"},  # planted violation
            }
        ]
    }

    with pytest.raises(AssertionError) as excinfo:
        assert_no_pii(
            poisoned_payload,
            forbidden_keys=FORBIDDEN_USER_KEYS,
            forbidden_strings=set(),
        )

    # Sanity-check the error message points at the offending JSONPath.
    assert "user_id" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Hub-dependent tests — skip until #449 ships.
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    not _HUB_AVAILABLE,
    reason="hub routes not yet implemented (#449)",
)
@pytest.mark.asyncio
async def test_get_group_posts_response_contains_no_user_pii() -> None:
    """GET /api/v1/hub/groups/{id}/posts must contain ZERO user-table fields."""
    # Imports are deferred to test-body so collection works even when these
    # symbols don't yet exist (the skipif gate above prevents the body from
    # running in that case).
    import httpx  # noqa: WPS433

    from src.main import app  # noqa: WPS433
    from src.services.database.user_repository import UserRepository  # noqa: WPS433

    user_repo = UserRepository()
    user = await user_repo.create_user(
        username=_CANARY_USERNAME,
        email=_CANARY_EMAIL,
        password_hash="not-a-real-hash",  # noqa: S106 - test fixture
        display_name=_CANARY_DISPLAY_NAME,
    )

    # Seed group + post via hub repository (introduced by #449).
    # If these symbols don't exist at runtime we still want the test to
    # surface a meaningful failure rather than silently pass.
    from src.services.database import hub_repository  # type: ignore  # noqa: WPS433

    group = await hub_repository.create_group(  # type: ignore[attr-defined]
        owner_user_id=user.user_id,
        name="canary-group",
    )
    await hub_repository.create_post(  # type: ignore[attr-defined]
        group_id=group["group_id"],
        author_user_id=user.user_id,
        body="canary post",
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get(
            f"/api/v1/hub/groups/{group['group_id']}/posts"
        )

    assert response.status_code == 200, response.text
    payload = response.json()

    canary_strings = {
        _CANARY_EMAIL,
        _CANARY_DISPLAY_NAME,
        _CANARY_USERNAME,
        user.user_id,
    }

    assert_no_pii(
        payload,
        forbidden_keys=FORBIDDEN_USER_KEYS,
        forbidden_strings=canary_strings,
    )


@pytest.mark.skipif(
    not _HUB_AVAILABLE,
    reason="hub routes not yet implemented (#449)",
)
@pytest.mark.asyncio
async def test_get_group_detail_response_contains_no_user_pii() -> None:
    """GET /api/v1/hub/groups/{id} must contain ZERO user-table fields."""
    import httpx  # noqa: WPS433

    from src.main import app  # noqa: WPS433
    from src.services.database.user_repository import UserRepository  # noqa: WPS433

    user_repo = UserRepository()
    user = await user_repo.create_user(
        username=_CANARY_USERNAME + "_detail",
        email=_CANARY_EMAIL,
        password_hash="not-a-real-hash",  # noqa: S106 - test fixture
        display_name=_CANARY_DISPLAY_NAME,
    )

    from src.services.database import hub_repository  # type: ignore  # noqa: WPS433

    group = await hub_repository.create_group(  # type: ignore[attr-defined]
        owner_user_id=user.user_id,
        name="canary-group-detail",
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get(f"/api/v1/hub/groups/{group['group_id']}")

    assert response.status_code == 200, response.text
    payload = response.json()

    canary_strings = {
        _CANARY_EMAIL,
        _CANARY_DISPLAY_NAME,
        _CANARY_USERNAME + "_detail",
        user.user_id,
    }

    assert_no_pii(
        payload,
        forbidden_keys=FORBIDDEN_USER_KEYS,
        forbidden_strings=canary_strings,
    )
