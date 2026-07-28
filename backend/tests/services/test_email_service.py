"""SMTP email service tests."""

import pytest

from backend.src.services import email_service


@pytest.mark.asyncio
async def test_parent_approval_email_builds_safe_plain_and_html_content(monkeypatch):
    captured = {}

    def capture(settings, message):
        captured["settings"] = settings
        captured["message"] = message

    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("EMAIL_FROM", "Creative Workshop <no-reply@example.test>")
    monkeypatch.setenv("SMTP_USE_TLS", "1")
    monkeypatch.setattr(email_service, "_send_smtp", capture)

    await email_service.send_parent_approval_email(
        parent_email="parent@example.test",
        child_name="A <kid>",
        approval_url="https://creative.example.test/parent-approval?token=abc",
    )

    message = captured["message"]
    assert message["To"] == "parent@example.test"
    assert "A <kid>" in message.get_body(preferencelist=("plain",)).get_content()
    assert "&lt;kid&gt;" in message.get_body(preferencelist=("html",)).get_content()


@pytest.mark.asyncio
async def test_parent_approval_email_requires_smtp_configuration(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("EMAIL_FROM", raising=False)

    with pytest.raises(email_service.EmailDeliveryNotConfigured):
        await email_service.send_parent_approval_email(
            parent_email="parent@example.test",
            child_name="Kid",
            approval_url="https://creative.example.test/approval",
        )


@pytest.mark.asyncio
async def test_parent_approval_email_prefers_resend_when_configured(monkeypatch):
    captured = {}

    def capture(settings, message):
        captured["settings"] = settings
        captured["message"] = message

    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("EMAIL_FROM", "Creative Workshop <no-reply@example.test>")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.setattr(email_service, "_send_resend", capture)

    await email_service.send_parent_approval_email(
        parent_email="parent@example.test",
        child_name="Kid",
        approval_url="https://creative.example.test/approval",
    )

    assert captured["settings"].api_key == "re_test_key"
    assert captured["message"]["To"] == "parent@example.test"
