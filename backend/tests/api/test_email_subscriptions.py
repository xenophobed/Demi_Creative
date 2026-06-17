"""Contract tests for the public Kids Daily email subscription route.

Locks the API contract for ``POST /api/v1/email-subscriptions/kids-daily``:
the public homepage hands an email to this endpoint to opt into Kids Daily
preview emails. The route is intentionally auth-free (a visitor, not a
logged-in parent, subscribes), so these tests assert the contract that the
frontend ``emailSubscriptionService`` depends on:

  * a valid email returns 201 with a normalized echo + ``message``
  * the email is normalized (trimmed + lowercased) before storage
  * re-subscribing the same email is idempotent (upsert, not a 500)
  * a malformed email is rejected at the validation boundary (422)

We assert behaviour through the HTTP layer rather than the DB so the test
survives a future repository refactor — the contract is the response, not
the storage mechanism.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.src.main import app


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
class TestKidsDailyEmailSubscription:
    """Contract for POST /api/v1/email-subscriptions/kids-daily."""

    async def test_valid_email_subscribes_and_echoes_contract(self):
        """A valid email returns 201 with the documented response shape."""
        async with _client() as client:
            resp = await client.post(
                "/api/v1/email-subscriptions/kids-daily",
                json={"email": "parent.happy@example.com"},
            )

        assert resp.status_code == 201
        body = resp.json()
        # Downstream emailSubscriptionService reads exactly these keys.
        assert body["email"] == "parent.happy@example.com"
        assert body["message"] == "subscribed"
        assert body["subscribed_at"]  # present + truthy timestamp

    async def test_email_is_normalized_before_storage(self):
        """Mixed-case / padded input is trimmed and lowercased.

        Normalization is what makes the unique-email upsert meaningful:
        "USER@X.com" and "user@x.com " must collapse to one subscriber,
        so the echoed email proves the normalizer ran.
        """
        async with _client() as client:
            resp = await client.post(
                "/api/v1/email-subscriptions/kids-daily",
                json={"email": "  Parent.CASE@Example.COM  "},
            )

        assert resp.status_code == 201
        assert resp.json()["email"] == "parent.case@example.com"

    async def test_resubscribe_is_idempotent(self):
        """Subscribing the same email twice upserts — never a 500.

        The route's ``ON CONFLICT(email) DO UPDATE`` is the guard against a
        duplicate-key crash. Two identical posts must both succeed and echo
        the same address.
        """
        payload = {"email": "parent.repeat@example.com"}
        async with _client() as client:
            first = await client.post(
                "/api/v1/email-subscriptions/kids-daily", json=payload
            )
            second = await client.post(
                "/api/v1/email-subscriptions/kids-daily", json=payload
            )

        assert first.status_code == 201
        assert second.status_code == 201
        assert second.json()["email"] == "parent.repeat@example.com"

    @pytest.mark.parametrize(
        "bad_email",
        ["notanemail", "missing@domain", "@nodomain.com", "spaces in@x.com", ""],
    )
    async def test_malformed_email_is_rejected(self, bad_email):
        """Invalid emails fail Pydantic validation with 422 (never reach DB)."""
        async with _client() as client:
            resp = await client.post(
                "/api/v1/email-subscriptions/kids-daily",
                json={"email": bad_email},
            )

        assert resp.status_code == 422
