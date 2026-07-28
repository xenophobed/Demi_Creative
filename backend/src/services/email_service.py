"""Transactional email delivery for account workflows."""

from __future__ import annotations

import asyncio
import os
import smtplib
import ssl
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage
from html import escape


class EmailDeliveryError(RuntimeError):
    """Raised when an email cannot be accepted by the configured provider."""


class EmailDeliveryNotConfigured(EmailDeliveryError):
    """Raised when the application has no usable email provider settings."""


@dataclass(frozen=True)
class SMTPSettings:
    host: str
    port: int
    username: str | None
    password: str | None
    sender: str
    use_tls: bool
    use_ssl: bool
    reply_to: str | None = None


@dataclass(frozen=True)
class ResendSettings:
    api_key: str
    sender: str
    api_url: str
    reply_to: str | None = None


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _smtp_settings() -> SMTPSettings:
    host = os.getenv("SMTP_HOST", "").strip()
    sender = (os.getenv("EMAIL_FROM") or os.getenv("SMTP_USERNAME") or "").strip()
    if not host or not sender:
        raise EmailDeliveryNotConfigured(
            "Parent approval email delivery is not configured"
        )

    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError as exc:
        raise EmailDeliveryNotConfigured("SMTP_PORT must be an integer") from exc

    use_ssl = _env_bool("SMTP_USE_SSL", False)
    use_tls = _env_bool("SMTP_USE_TLS", not use_ssl)
    if use_ssl and use_tls:
        raise EmailDeliveryNotConfigured(
            "SMTP_USE_SSL and SMTP_USE_TLS cannot both be enabled"
        )

    return SMTPSettings(
        host=host,
        port=port,
        username=os.getenv("SMTP_USERNAME") or None,
        password=os.getenv("SMTP_PASSWORD") or None,
        sender=sender,
        use_tls=use_tls,
        use_ssl=use_ssl,
        reply_to=os.getenv("EMAIL_REPLY_TO") or None,
    )


def _resend_settings() -> ResendSettings | None:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    if not api_key:
        return None

    sender = os.getenv("EMAIL_FROM", "").strip()
    if not sender:
        raise EmailDeliveryNotConfigured(
            "EMAIL_FROM is required when RESEND_API_KEY is configured"
        )

    return ResendSettings(
        api_key=api_key,
        sender=sender,
        api_url=os.getenv("RESEND_API_URL", "https://api.resend.com/emails").strip(),
        reply_to=os.getenv("EMAIL_REPLY_TO") or None,
    )


def _build_parent_approval_message(
    *,
    settings: SMTPSettings,
    parent_email: str,
    child_name: str,
    approval_url: str,
    expires_in_hours: int,
) -> EmailMessage:
    safe_child_name = escape(child_name)
    message = EmailMessage()
    message["From"] = settings.sender
    message["To"] = parent_email
    message["Subject"] = f"Parent approval needed for {child_name}"
    if settings.reply_to:
        message["Reply-To"] = settings.reply_to
    message.set_content(
        f"A child account for {child_name} is waiting for your approval.\n\n"
        f"Approve the account here: {approval_url}\n\n"
        f"This link expires in {expires_in_hours} hours. If you did not expect "
        "this request, you can safely ignore this email."
    )
    message.add_alternative(
        f"<html><body><p>A child account for <strong>{safe_child_name}</strong> "
        "is waiting for your approval.</p>"
        f'<p><a href="{escape(approval_url, quote=True)}">Approve this account</a></p>'
        f"<p>This link expires in {expires_in_hours} hours. If you did not expect "
        "this request, you can safely ignore this email.</p></body></html>",
        subtype="html",
    )
    return message


def _send_smtp(settings: SMTPSettings, message: EmailMessage) -> None:
    smtp_class = smtplib.SMTP_SSL if settings.use_ssl else smtplib.SMTP
    context = ssl.create_default_context()
    with smtp_class(settings.host, settings.port, timeout=15) as server:
        if settings.use_tls:
            server.starttls(context=context)
        if settings.username:
            server.login(settings.username, settings.password or "")
        server.send_message(message)


def _send_resend(settings: ResendSettings, message: EmailMessage) -> None:
    html_part = message.get_body(preferencelist=("html", "plain"))
    payload = {
        "from": settings.sender,
        "to": [str(address) for address in message["To"].split(",")],
        "subject": message["Subject"],
        "text": message.get_body(preferencelist=("plain", "html")).get_content(),
        "html": html_part.get_content() if html_part.get_content_type() == "text/html" else None,
    }
    if settings.reply_to:
        payload["reply_to"] = [settings.reply_to]

    request = urllib.request.Request(
        settings.api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "creative-agent/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        if not 200 <= response.status < 300:
            raise EmailDeliveryError("Resend provider rejected the email")


async def send_parent_approval_email(
    *,
    parent_email: str,
    child_name: str,
    approval_url: str,
    expires_in_hours: int = 72,
) -> None:
    """Send an approval email and fail if the provider did not accept it."""
    resend_settings = _resend_settings()
    if resend_settings:
        message_settings = SMTPSettings(
            host="resend",
            port=443,
            username=None,
            password=None,
            sender=resend_settings.sender,
            use_tls=False,
            use_ssl=False,
            reply_to=resend_settings.reply_to,
        )
        message = _build_parent_approval_message(
            settings=message_settings,
            parent_email=parent_email,
            child_name=child_name,
            approval_url=approval_url,
            expires_in_hours=expires_in_hours,
        )
        try:
            await asyncio.to_thread(_send_resend, resend_settings, message)
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise EmailDeliveryError("Resend provider rejected the email") from exc
        return

    settings = _smtp_settings()
    message = _build_parent_approval_message(
        settings=settings,
        parent_email=parent_email,
        child_name=child_name,
        approval_url=approval_url,
        expires_in_hours=expires_in_hours,
    )
    try:
        await asyncio.to_thread(_send_smtp, settings, message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("SMTP provider rejected the email") from exc
