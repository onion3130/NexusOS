"""Outbound SMTP email channel for notification delivery."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import Settings

SMTP_TIMEOUT_SECONDS = 15.0


class EmailDeliveryError(ValueError):
    """Raised when a notification email cannot be sent."""


def send_email(settings: Settings, *, to: str, subject: str, body: str) -> None:
    """Send one bounded notification email through the configured SMTP relay."""
    host = settings.notification_email_smtp_host
    from_address = settings.notification_email_from
    if not host or not from_address or not to:
        raise EmailDeliveryError("email_channel_not_configured")
    message = EmailMessage()
    message["From"] = from_address
    message["To"] = to
    message["Subject"] = subject[:120]
    message.set_content(body[:2000])
    try:
        with smtplib.SMTP(host, settings.notification_email_smtp_port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            if settings.notification_email_use_tls:
                smtp.starttls()
            user = settings.notification_email_smtp_user
            password = settings.notification_email_smtp_password.get_secret_value() if settings.notification_email_smtp_password else None
            if user and password:
                smtp.login(user, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("email_send_failed") from exc
