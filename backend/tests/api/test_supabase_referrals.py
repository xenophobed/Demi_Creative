"""Supabase referral signup tests.

These cover the production auth path where referral codes arrive through
Supabase signUp user metadata and are handled while syncing the local user row.
"""

import importlib

import pytest
import pytest_asyncio

from backend.src.api import deps
from backend.src.services.database.child_profile_repository import ChildProfileRepository
from backend.src.services.database.connection import DatabaseManager
from backend.src.services.database.referral_repository import ReferralRepository
from backend.src.services.database.schema import init_schema
from backend.src.services.database.user_repository import UserRepository
from backend.src.services.supabase_auth import SupabaseClaims


@pytest_asyncio.fixture
async def referral_env(monkeypatch):
    db = DatabaseManager(":memory:")
    await db.connect()
    await init_schema(db)

    user_repo = UserRepository()
    user_repo._db = db
    ref_repo = ReferralRepository()
    ref_repo._db = db
    child_repo = ChildProfileRepository(db)

    monkeypatch.setattr(deps, "db_manager", db)
    monkeypatch.setattr(deps, "user_repo", user_repo)
    monkeypatch.setattr(deps, "referral_repo", ref_repo)
    monkeypatch.setattr(deps, "child_profile_repo", child_repo)

    user_service_module = importlib.import_module("backend.src.services.user_service")
    original_repo = user_service_module.user_service._repo
    original_db = user_service_module.user_service._db
    monkeypatch.setattr(user_service_module, "referral_repo", ref_repo)
    user_service_module.user_service._repo = user_repo
    user_service_module.user_service._db = db

    yield {
        "db": db,
        "user_repo": user_repo,
        "ref_repo": ref_repo,
        "user_service_module": user_service_module,
        "original_repo": original_repo,
        "original_db": original_db,
    }

    user_service_module.user_service._repo = original_repo
    user_service_module.user_service._db = original_db
    await db.disconnect()


def _claims(
    *,
    sub: str,
    email: str,
    referral_code: str | None = None,
    email_confirmed: bool = False,
) -> SupabaseClaims:
    return SupabaseClaims(
        sub=sub,
        email=email,
        email_confirmed=email_confirmed,
        referral_code=referral_code,
        role="parent",
    )


async def _create_referrer(user_repo: UserRepository):
    return await user_repo.create_user(
        username="referrer",
        email="referrer@test.com",
        password_hash="hash",
        role="parent",
        consent_status="not_required",
    )


@pytest.mark.asyncio
async def test_supabase_signup_metadata_creates_pending_referral(referral_env):
    referrer = await _create_referrer(referral_env["user_repo"])

    user = await deps._get_or_create_supabase_user(
        _claims(
            sub="supabase-referred",
            email="referred@test.com",
            referral_code=referrer.referral_code,
            email_confirmed=False,
        )
    )

    assert user is not None
    assert user.referred_by == referrer.referral_code

    referral = await referral_env["ref_repo"].get_referral_by_referred_user(user.user_id)
    assert referral is not None
    assert referral["referrer_user_id"] == referrer.user_id
    assert referral["referral_code"] == referrer.referral_code
    assert referral["is_qualified"] == 0


@pytest.mark.asyncio
async def test_supabase_confirmed_signup_qualifies_and_promotes_at_threshold(
    referral_env,
):
    user_repo = referral_env["user_repo"]
    ref_repo = referral_env["ref_repo"]
    referrer = await _create_referrer(user_repo)

    for i in range(9):
        referred = await user_repo.create_user(
            username=f"existing_ref_{i}",
            email=f"existing_ref_{i}@test.com",
            password_hash="hash",
            role="parent",
            consent_status="not_required",
            referred_by=referrer.referral_code,
        )
        await ref_repo.create_referral(
            referrer_user_id=referrer.user_id,
            referred_user_id=referred.user_id,
            referral_code=referrer.referral_code,
        )
        await ref_repo.qualify_referral(referred.user_id)

    user = await deps._get_or_create_supabase_user(
        _claims(
            sub="supabase-tenth-referral",
            email="tenth@test.com",
            referral_code=referrer.referral_code,
            email_confirmed=True,
        )
    )

    assert user is not None
    referral = await ref_repo.get_referral_by_referred_user(user.user_id)
    assert referral is not None
    assert referral["is_qualified"] == 1

    promoted = await user_repo.get_by_id(referrer.user_id)
    assert promoted is not None
    assert promoted.membership_tier == "plus"
