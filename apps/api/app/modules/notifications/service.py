"""Notification channel settings, enqueue, resend, and delivery service."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.core.config import Settings, get_settings
from app.db.base import utc_now
from app.db.models import Notification, NotificationChannelDelivery
from app.modules.identity.service import add_audit_event
from app.modules.notifications.channels import configured_channels, send
from app.modules.notifications.schemas import ChannelDeliveryResponse, NotificationSettingsResponse, TestSendResult


def enqueue_deliveries(db: OrmSession, notification: Notification, settings: Settings | None = None) -> int:
    """Create one pending delivery row per enabled channel for a notification."""
    active = get_settings() if settings is None else settings
    created = 0
    for channel in configured_channels(active):
        existing = db.scalar(
            select(NotificationChannelDelivery.id).where(
                NotificationChannelDelivery.notification_id == notification.id,
                NotificationChannelDelivery.channel == channel,
            )
        )
        if existing is None:
            db.add(NotificationChannelDelivery(notification_id=notification.id, channel=channel, status="pending", available_at=utc_now()))
            created += 1
    if created:
        db.flush()
    return created


def resend_deliveries(db: OrmSession, user_id: str, notification_id: str) -> Notification | None:
    """Requeue owned channel deliveries for one persisted notification."""
    notification = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id))
    if notification is None:
        return None
    active = configured_channels(get_settings())
    rows = db.scalars(select(NotificationChannelDelivery).where(NotificationChannelDelivery.notification_id == notification.id)).all()
    for row in rows:
        if row.channel in active:
            row.status = "pending"
            row.attempts = 0
            row.available_at = utc_now()
            row.locked_until = None
            row.last_error_code = None
            row.delivered_at = None
    existing = {row.channel for row in rows}
    for channel in active:
        if channel not in existing:
            db.add(NotificationChannelDelivery(notification_id=notification.id, channel=channel, status="pending", available_at=utc_now()))
    add_audit_event(db, action="notifications.resend", result="success", actor_user_id=user_id, target=notification.id)
    db.commit()
    return notification


def delivery_responses(notification: Notification) -> list[ChannelDeliveryResponse]:
    """Map owned delivery rows to bounded public responses in channel order."""
    return [
        ChannelDeliveryResponse(channel=item.channel, status=item.status, delivered_at=item.delivered_at, error_code=item.last_error_code)
        for item in sorted(notification.deliveries, key=lambda item: item.channel)
    ]


def settings_status(settings: Settings) -> NotificationSettingsResponse:
    """Expose channel configuration without any secret values."""
    password = settings.notification_email_smtp_password
    token = settings.notification_push_token
    return NotificationSettingsResponse(
        email_enabled=settings.notification_email_enabled,
        email_configured=bool(settings.notification_email_smtp_host and settings.notification_email_from and settings.notification_email_to),
        email_smtp_host=settings.notification_email_smtp_host,
        email_smtp_user=settings.notification_email_smtp_user,
        email_from=settings.notification_email_from,
        email_to=settings.notification_email_to,
        email_credentials_set=bool(settings.notification_email_smtp_user and password and password.get_secret_value()),
        push_enabled=settings.notification_push_enabled,
        push_configured=bool(settings.notification_push_url and settings.notification_push_topic),
        push_url=settings.notification_push_url,
        push_topic=settings.notification_push_topic,
        push_token_set=bool(token and token.get_secret_value()),
    )


def send_test(db: OrmSession | None, settings: Settings, *, user_id: str | None = None) -> list[TestSendResult]:
    """Send one bounded test message through every enabled channel."""
    test_notification = SimpleNamespace(
        title="NexusOS test notification",
        body="This is a test from NexusOS. Your notification channels are working.",
    )
    results: list[TestSendResult] = []
    for channel in configured_channels(settings):
        try:
            send(settings, channel, notification=test_notification)  # type: ignore[arg-type]
            results.append(TestSendResult(channel=channel, ok=True))
        except (OSError, ValueError) as exc:
            results.append(TestSendResult(channel=channel, ok=False, error_code=str(exc) or "delivery_failed"))
    if results and db is not None and user_id:
        add_audit_event(
            db,
            action="notifications.test_send",
            result="success" if all(item.ok for item in results) else "failure",
            actor_user_id=user_id,
            metadata={"channels": [item.channel for item in results], "ok": [item.channel for item in results if item.ok]},
        )
        db.commit()
    return results
