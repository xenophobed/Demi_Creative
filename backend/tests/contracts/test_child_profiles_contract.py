"""
Child Profiles Contract Tests (#544, #549)

Locks the backend contract consumed by parallel frontend work:
  - GET/POST/PATCH/default/archive routes and response shapes.
  - Parent-only management.
  - Cross-account child IDs return generic 404s.
  - Registration-created default child profiles are listable.
  - Migration backfills users.default_child_id into child_profiles.
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
from backend.src.services.database.user_repository import UserData, UserRepository
from backend.src.services.user_service import UserService


PARENT_A = UserData(
    user_id="profiles_parent_a",
    username="profiles_parent_a",
    email="parent-a@test.com",
    password_hash="h",
    display_name="Parent A",
    role="parent",
    created_at="",
    updated_at="",
)

PARENT_B = UserData(
    user_id="profiles_parent_b",
    username="profiles_parent_b",
    email="parent-b@test.com",
    password_hash="h",
    display_name="Parent B",
    role="parent",
    created_at="",
    updated_at="",
)

CHILD_USER = UserData(
    user_id="profiles_child",
    username="profiles_child",
    email="child@test.com",
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


def _valid_create(**overrides) -> dict:
    body = {
        "child_id": "child_alpha",
        "name": "Ada",
        "age_group": "6-8",
        "interests": ["Space", "Music"],
        "avatar": "rocket",
        "is_default": True,
    }
    body.update(overrides)
    return body


class TestChildProfileEndpoints:
    @pytest.mark.asyncio
    async def test_parent_can_create_list_patch_set_default_and_archive(self, client):
        created = await client.post("/api/v1/child-profiles", json=_valid_create())
        assert created.status_code == 201, created.text
        payload = created.json()
        assert payload["child_id"] == "child_alpha"
        assert payload["user_id"] == PARENT_A.user_id
        assert payload["name"] == "Ada"
        assert payload["age_group"] == "6-8"
        assert payload["interests"] == ["Space", "Music"]
        assert payload["is_default"] is True

        listing = await client.get("/api/v1/child-profiles")
        assert listing.status_code == 200
        assert listing.json()["items"][0]["child_id"] == "child_alpha"

        patched = await client.patch(
            "/api/v1/child-profiles/child_alpha",
            json={"name": "Milo", "age_group": "9-12", "interests": ["Robots"]},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["name"] == "Milo"
        assert patched.json()["age_group"] == "9-12"

        second = await client.post(
            "/api/v1/child-profiles",
            json=_valid_create(
                child_id="child_beta",
                name="Bea",
                is_default=False,
            ),
        )
        assert second.status_code == 201, second.text

        defaulted = await client.post("/api/v1/child-profiles/child_beta/default")
        assert defaulted.status_code == 200, defaulted.text
        assert defaulted.json()["is_default"] is True

        user_row = await db_manager.fetchone(
            "SELECT default_child_id FROM users WHERE user_id = ?",
            (PARENT_A.user_id,),
        )
        assert user_row["default_child_id"] == "child_beta"

        archived = await client.post("/api/v1/child-profiles/child_beta/archive")
        assert archived.status_code == 200, archived.text
        assert archived.json()["archived_at"] is not None
        assert archived.json()["is_default"] is False

        listing = await client.get("/api/v1/child-profiles")
        assert [item["child_id"] for item in listing.json()["items"]] == ["child_alpha"]

    @pytest.mark.asyncio
    async def test_child_role_cannot_manage_profiles(self, client):
        _current_user["user"] = CHILD_USER
        create = await client.post("/api/v1/child-profiles", json=_valid_create())
        assert create.status_code == 403
        assert create.json()["detail"]["code"] == "PARENT_ROLE_REQUIRED"

        patch = await client.patch(
            "/api/v1/child-profiles/child_alpha",
            json={"name": "Nope"},
        )
        assert patch.status_code == 403

        set_default = await client.post("/api/v1/child-profiles/child_alpha/default")
        assert set_default.status_code == 403

        archive = await client.post("/api/v1/child-profiles/child_alpha/archive")
        assert archive.status_code == 403

    @pytest.mark.asyncio
    async def test_cross_account_child_ids_return_generic_not_found(self, client):
        other_repo = ChildProfileRepository(db_manager)
        await other_repo.create(
            user_id=PARENT_B.user_id,
            child_id="shared_visible_only_to_b",
            name="Other",
            age_group="6-8",
            is_default=True,
        )

        patch = await client.patch(
            "/api/v1/child-profiles/shared_visible_only_to_b",
            json={"name": "Leak?"},
        )
        assert patch.status_code == 404
        assert patch.json()["detail"]["code"] == "CHILD_PROFILE_NOT_FOUND"

        set_default = await client.post(
            "/api/v1/child-profiles/shared_visible_only_to_b/default"
        )
        assert set_default.status_code == 404

        archive = await client.post(
            "/api/v1/child-profiles/shared_visible_only_to_b/archive"
        )
        assert archive.status_code == 404

        other = await other_repo.get_for_user(PARENT_B.user_id, "shared_visible_only_to_b")
        assert other.name == "Other"
        assert other.is_default is True

    @pytest.mark.asyncio
    async def test_obvious_pii_in_child_nickname_is_rejected(self, client):
        email_name = await client.post(
            "/api/v1/child-profiles",
            json=_valid_create(child_id="pii_email", name="kid@example.com"),
        )
        assert email_name.status_code == 422

        phone_name = await client.post(
            "/api/v1/child-profiles",
            json=_valid_create(child_id="pii_phone", name="555-123-4567"),
        )
        assert phone_name.status_code == 422


class TestRegistrationAndMigration:
    @pytest.mark.asyncio
    async def test_parent_registration_created_profile_is_visible(self, test_db):
        user_repo = UserRepository()
        user_repo._db = db_manager
        svc = UserService()
        svc._repo = user_repo
        svc._db = db_manager

        result = await svc.register(
            username="registered_parent",
            email="registered-parent@test.com",
            password="password123",
            child_id="registration_child",
            child_name="Nova",
            child_age_group="3-5",
            child_interests=["Drawing"],
        )

        assert result.success is True
        assert result.user.default_child_id == "registration_child"

        profiles = await child_profile_repo.list_for_user(result.user.user_id)
        assert len(profiles) == 1
        assert profiles[0].child_id == "registration_child"
        assert profiles[0].name == "Nova"
        assert profiles[0].age_group == "3-5"
        assert profiles[0].interests == ["Drawing"]
        assert profiles[0].is_default is True

    @pytest.mark.asyncio
    async def test_schema_backfills_default_child_id(self, test_db):
        now = datetime.now().isoformat()
        await db_manager.execute(
            """
            INSERT INTO users (
                user_id, username, email, password_hash, display_name,
                is_active, is_verified, role, consent_status,
                membership_tier, referral_code, created_at, updated_at,
                default_child_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy_parent",
                "legacy_parent",
                "legacy@test.com",
                "h",
                "Legacy Kid",
                1,
                1,
                "parent",
                "not_required",
                "free",
                "LEGACY01",
                now,
                now,
                "legacy_child",
            ),
        )
        await db_manager.commit()

        await init_schema(db_manager)

        profiles = await child_profile_repo.list_for_user("legacy_parent")
        assert len(profiles) == 1
        assert profiles[0].child_id == "legacy_child"
        assert profiles[0].name == "Legacy Kid"
        assert profiles[0].is_default is True
