"""Dedicated bounded worker processing for outbound notification deliveries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session as OrmSession

from app.core.config import Settings
from app.db.base import utc_now
from app.db.models import Notification, NotificationChannelDelivery
from app.modules.identity.service import add_audit_event
from app.modules.notifications.channels import configured_channels, send

MAX_ATTEMPTS = 3
LEASE = timedelta(minutes=5)


def _current_time(now: datetime | None) -> datetime:
    """Normalize an optional test clock to aware UTC."""
    value = now or utc_now()
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _fail_exhausted(db: OrmSession, current: datetime) -> None:
    """Terminally fail stale delivery leases after the retry limit."""
    items = db.scalars(
        select(NotificationChannelDelivery).where(
            NotificationChannelDelivery.status == "processing",
            NotificationChannelDelivery.locked_until <= current,
            NotificationChannelDelivery.attempts >= MAX_ATTEMPTS,
        )
    ).all()
    for item in items:
        item.status = "failed"
        item.last_error_code = "worker_retry_limit"
        item.locked_until = None
        notification = db.get(Notification, item.notification_id)
        if notification is not None:
            add_audit_event(
                db,
                action="notifications.deliver",
                result="failure",
                actor_user_id=notification.user_id,
                target=notification.id,
                metadata={"channel": item.channel, "error": "worker_retry_limit"},
            )
    if items:
        db.commit()


def process_notification_deliveries(
    db: OrmSession,
    *,
    settings: Settings,
    now: datetime | None = None,
    batch_size: int = 20,
) -> int:
    """Claim and deliver one bounded batch of pending channel deliveries."""
    current = _current_time(now)
    _fail_exhausted(db, current)
    processed = 0
    for _ in range(max(1, min(batch_size, 100))):
        candidate = db.scalar(
            select(NotificationChannelDelivery.id)
            .where(
                NotificationChannelDelivery.attempts < MAX_ATTEMPTS,
                NotificationChannelDelivery.available_at <= current,
                or_(
                    NotificationChannelDelivery.status == "pending",
                    (NotificationChannelDelivery.status == "processing") & (NotificationChannelDelivery.locked_until <= current),
                ),
            )
            .order_by(NotificationChannelDelivery.created_at)
            .limit(1)
        )
        if candidate is None:
            break
        claim = db.execute(
            update(NotificationChannelDelivery)
            .where(
                NotificationChannelDelivery.id == candidate,
                NotificationChannelDelivery.attempts < MAX_ATTEMPTS,
                NotificationChannelDelivery.available_at <= current,
                or_(
                    NotificationChannelDelivery.status == "pending",
                    (NotificationChannelDelivery.status == "processing") & (NotificationChannelDelivery.locked_until <= current),
                ),
            )
            .values(status="processing", attempts=NotificationChannelDelivery.attempts + 1, locked_until=current + LEASE)
        )
        db.commit()
        if claim.rowcount != 1:
            continue
        item = db.get(NotificationChannelDelivery, candidate)
        if item is None:
            continue
        notification = db.get(Notification, item.notification_id)
        if notification is None:
            item.status = "failed"
            item.last_error_code = "notification_unavailable"
            item.locked_until = None
            db.commit()
            processed += 1
            continue
        if item.channel not in configured_channels(settings):
            item.status = "skipped"
            item.locked_until = None
            db.commit()
            processed += 1
            continue
        try:
            send(settings, item.channel, notification=notification)
        except (OSError, ValueError) as exc:
            error_code = str(exc) or "delivery_failed"
            item.status = "failed" if item.attempts >= MAX_ATTEMPTS else "pending"
            item.available_at = current + timedelta(seconds=30 * item.attempts)
            item.locked_until = None
            item.last_error_code = error_code
            if item.status == "failed":
                add_audit_event(
                    db,
                    action="notifications.deliver",
                    result="failure",
                    actor_user_id=notification.user_id,
                    target=notification.id,
                    metadata={"channel": item.channel, "error": error_code, "attempt": item.attempts},
                )
        else:
            item.status = "delivered"
            item.delivered_at = current
            item.locked_until = None
            item.last_error_code = None
            add_audit_event(
                db,
                action="notifications.deliver",
                result="success",
                actor_user_id=notification.user_id,
                target=notification.id,
                metadata={"channel": item.channel},
            )
        db.commit()
        processed += 1
    return processed
