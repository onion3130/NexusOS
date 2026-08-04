"""Outbound notification channel adapters: email (SMTP) and push (ntfy)."""

from __future__ import annotations

from app.core.config import Settings
from app.db.models import Notification


def configured_channels(settings: Settings) -> tuple[str, ...]:
    """Return enabled channel keys in stable, documented order."""
    channels: list[str] = []
    if settings.notification_email_enabled:
        channels.append("email")
    if settings.notification_push_enabled:
        channels.append("push")
    return tuple(channels)


def send(settings: Settings, channel: str, *, notification: Notification) -> None:
    """Dispatch one notification through one enabled channel or raise ValueError."""
    if channel == "email":
        from app.modules.notifications.channels.email import send_email

        if not settings.notification_email_to:
            raise ValueError("email_channel_not_configured")
        send_email(settings, to=settings.notification_email_to, subject=notification.title, body=notification.body)
        return
    if channel == "push":
        from app.modules.notifications.channels.push import send_push

        send_push(settings, title=notification.title, body=notification.body)
        return
    raise ValueError("unknown_notification_channel")
