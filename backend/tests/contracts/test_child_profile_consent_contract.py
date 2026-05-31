"""
Child Profile Consent Contract Tests (#587)

Locks the backend contract for camera_consent and microphone_consent flags
on child_profiles, including the PATCH /consent endpoint and the schema
migration that adds the columns.

Reasons these tests exist:
  - Consent flags gate camera/mic surfaces (epic #579, PRD §3.15) — UI
    treats them as the source of truth, so the API response shape must
    include them and default to false.
  - Only parent-role users may flip the flags. A forged request from a
    child-role token must be rejected with the same PARENT_ROLE_REQUIRED
    code the rest of the child-profile API uses.
  - Cross-account access must return generic CHILD_PROFILE_NOT_FOUND so
    parent IDs can't be enumerated.
"""

from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.src.api.deps import get_current_user
from backend.src.main import app
from backend.src.services.database import child_profile_repo, db_manager
from backend.src.services.database.child_profile_repository import ChildProfileRepository
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.schema import init_schema
from backend.src.services.database.sql_compat import column_exists
from backend.src.services.database.user_repository import UserData


PARENT_A = UserData(
    user_id="consent_parent_a",
    username="consent_parent_a",
    email="parent-a@consent-test.com",
    password_hash="h",
    display_name="Parent A",
    role="parent",
    created_at="",
    updated_at="",
)

PARENT_B = UserData(
    user_id="consent_parent_b",
    username="consent_parent_b",
    email="parent-b@consent-test.com",
    password_hash="h",
    display_name="Parent B",
    role="parent",
    created_at="",
    updated_at="",
)

CHILD_USER = UserData(
    user_id="consent_child_user",
    username="consent_child_user",
    email="child@consent-test.com",
    password_hash="h",
    display_name="Child",
    role="child",
    parent_email="parent@test.com",
    consent_status="pending_parent_consent",
    created_at="",
    updated_at="",
)

_current_user = {"user": PARENT_A}


async def _override_current_user() -> UserData:
    return _current_user["user"]


@pytest_asyncio.fixture
async def test_db():
    fresh = DatabaseManager(":memory:")
    await fresh.connect()
    await init_schema(fresh)

    saved_adapter = db_manager._adapter
    db_manager._adapter = fresh._adapter

    now = datetime.now().isoformat()
    for user in (PARENT_A, PARENT_B, CHILD_USER):
        await db_manager.execute(
            """
            INSERT INTO users (
                user_id, username, email, password_hash, display_name,
                is_active, is_verified, role, parent_email, consent_status,
                membership_tier, referral_code, referred_by,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user.user_id,
                user.username,
                user.email,
                user.password_hash,
                user.display_name,
                1,
                1,
                user.role,
                user.parent_email,
                user.consent_status,
                "free",
                f"{user.user_id[-8:]:0<8}"[:8],
                None,
                now,
                now,
            ),
        )
    await db_manager.commit()

    yield fresh

    db_manager._adapter = saved_adapter
    await fresh.disconnect()


@pytest_asyncio.fixture
async def client(test_db):
    _current_user["user"] = PARENT_A
    app.dependency_overrides[get_current_user] = _override_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def child_profile(test_db):
    repo = ChildProfileRepository(db_manager)
    return await repo.create(
        user_id=PARENT_A.user_id,
        child_id="child_consent_alpha",
        name="Ada",
        age_group="6-8",
        is_default=True,
    )


class TestSchemaContract:
    @pytest.mark.asyncio
    async def test_camera_consent_column_exists(self, test_db):
        assert await column_exists(test_db, "child_profiles", "camera_consent")

    @pytest.mark.asyncio
    async def test_microphone_consent_column_exists(self, test_db):
        assert await column_exists(test_db, "child_profiles", "microphone_consent")

    @pytest.mark.asyncio
    async def test_create_defaults_both_flags_to_false(self, test_db, child_profile):
        assert child_profile.camera_consent is False
        assert child_profile.microphone_consent is False


class TestConsentResponseShape:
    @pytest.mark.asyncio
    async def test_get_includes_consent_flags(self, client, child_profile):
        listing = await client.get("/api/v1/child-profiles")
        assert listing.status_code == 200
        item = listing.json()["items"][0]
        assert item["camera_consent"] is False
        assert item["microphone_consent"] is False

    @pytest.mark.asyncio
    async def test_create_response_includes_consent_flags(self, client, test_db):
        created = await client.post(
            "/api/v1/child-profiles",
            json={
                "child_id": "child_consent_beta",
                "name": "Bea",
                "age_group": "6-8",
                "interests": [],
                "is_default": True,
            },
        )
        assert created.status_code == 201, created.text
        payload = created.json()
        assert payload["camera_consent"] is False
        assert payload["microphone_consent"] is False


class TestConsentPatchEndpoint:
    @pytest.mark.asyncio
    async def test_parent_can_grant_camera_consent(self, client, child_profile):
        response = await client.patch(
            f"/api/v1/child-profiles/{child_profile.child_id}/consent",
            json={"camera_consent": True},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["camera_consent"] is True
        assert body["microphone_consent"] is False

    @pytest.mark.asyncio
    async def test_parent_can_grant_microphone_consent(self, client, child_profile):
        response = await client.patch(
            f"/api/v1/child-profiles/{child_profile.child_id}/consent",
            json={"microphone_consent": True},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["microphone_consent"] is True
        assert body["camera_consent"] is False

    @pytest.mark.asyncio
    async def test_partial_update_preserves_other_flag(self, client, child_profile):
        first = await client.patch(
            f"/api/v1/child-profiles/{child_profile.child_id}/consent",
            json={"camera_consent": True},
        )
        assert first.status_code == 200
        assert first.json()["camera_consent"] is True

        second = await client.patch(
            f"/api/v1/child-profiles/{child_profile.child_id}/consent",
            json={"microphone_consent": True},
        )
        assert second.status_code == 200, second.text
        body = second.json()
        assert body["camera_consent"] is True
        assert body["microphone_consent"] is True

    @pytest.mark.asyncio
    async def test_parent_can_revoke_camera_consent(self, client, child_profile):
        await client.patch(
            f"/api/v1/child-profiles/{child_profile.child_id}/consent",
            json={"camera_consent": True},
        )
        revoked = await client.patch(
            f"/api/v1/child-profiles/{child_profile.child_id}/consent",
            json={"camera_consent": False},
        )
        assert revoked.status_code == 200, revoked.text
        assert revoked.json()["camera_consent"] is False

    @pytest.mark.asyncio
    async def test_empty_body_rejected(self, client, child_profile):
        response = await client.patch(
            f"/api/v1/child-profiles/{child_profile.child_id}/consent",
            json={},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_child_role_cannot_update_consent(self, client, child_profile):
        _current_user["user"] = CHILD_USER
        response = await client.patch(
            f"/api/v1/child-profiles/{child_profile.child_id}/consent",
            json={"camera_consent": True},
        )
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "PARENT_ROLE_REQUIRED"

    @pytest.mark.asyncio
    async def test_cross_account_consent_returns_generic_not_found(self, client, child_profile):
        other_repo = ChildProfileRepository(db_manager)
        await other_repo.create(
            user_id=PARENT_B.user_id,
            child_id="child_owned_by_b",
            name="Other",
            age_group="6-8",
            is_default=True,
        )

        response = await client.patch(
            "/api/v1/child-profiles/child_owned_by_b/consent",
            json={"camera_consent": True},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "CHILD_PROFILE_NOT_FOUND"

        other = await other_repo.get_for_user(PARENT_B.user_id, "child_owned_by_b")
        assert other.camera_consent is False
