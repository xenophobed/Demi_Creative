"""Parent approval email delivery contract tests."""

from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from backend.src.api.deps import get_current_user
from backend.src.api.models import ParentApprovalStatusResponse
from backend.src.api.routes import users as users_route
from backend.src.services.email_service import (
    EmailDeliveryError,
    EmailDeliveryNotConfigured,
)
from backend.src.services.database.user_repository import UserData


_PENDING_CHILD = UserData(
    user_id="pending_child_email",
    username="pending_child",
    email="child@example.com",
    password_hash="hash",
    display_name="Little Artist",
    role="child",
    parent_email="parent@example.com",
    consent_status="pending_parent_consent",
    created_at="2026-01-01T00:00:00",
    updated_at="2026-01-01T00:00:00",
)


async def _pending_child_user() -> UserData:
    return _PENDING_CHILD


@pytest.mark.asyncio
async def test_resend_sends_email_and_does_not_return_approval_token(test_client):
    from backend.src.main import app

    app.dependency_overrides[get_current_user] = _pending_child_user
    try:
        with patch.object(
            users_route,
            "send_parent_approval_email",
            new_callable=AsyncMock,
        ) as send_email:
            response = await test_client.post(
                "/api/v1/users/me/parent-approval/resend",
                headers={"Origin": "https://creative.demi-app.com"},
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200, response.text
    payload = ParentApprovalStatusResponse.model_validate(response.json())
    assert payload.email_sent is True
    assert payload.parent_email == "parent@example.com"
    assert "approval_url" not in response.json()
    assert "approval_token" not in response.json()
    send_email.assert_awaited_once()
    assert send_email.await_args.kwargs["parent_email"] == "parent@example.com"
    approval_url = send_email.await_args.kwargs["approval_url"]
    assert "https://creative.demi-app.com/parent-approval?token=" in approval_url
    token = parse_qs(urlparse(approval_url).query)["token"][0]
    payload, error = users_route.user_service._decode_parent_approval_token(token)
    assert error is None
    assert payload["sub"] == _PENDING_CHILD.user_id
    assert payload["parent_email"] == _PENDING_CHILD.parent_email


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (EmailDeliveryNotConfigured("missing SMTP"), 503),
        (EmailDeliveryError("provider rejected"), 502),
    ],
)
async def test_resend_reports_delivery_failure_without_claiming_success(
    test_client, error, expected_status
):
    from backend.src.main import app

    app.dependency_overrides[get_current_user] = _pending_child_user
    try:
        with patch.object(
            users_route,
            "send_parent_approval_email",
            new_callable=AsyncMock,
            side_effect=error,
        ):
            response = await test_client.post(
                "/api/v1/users/me/parent-approval/resend",
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == expected_status
    assert response.json()["detail"]
