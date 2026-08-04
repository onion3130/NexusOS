"""Bounded calendar event reminder processing for the NexusOS worker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session as OrmSession

from app.db.base import utc_now
from app.db.models import CalendarEvent, CalendarEventReminder, Notification
from app.modules.notifications.service import enqueue_deliveries


def process_due_event_reminders(db: OrmSession, *, now: datetime | None = None, batch_size: int = 50) -> int:
    """Atomically claim and deliver one bounded batch of due event reminders."""
    current = (now or utc_now()).astimezone(UTC)
    delivered = 0
    for _ in range(max(1, min(batch_size, 200))):
        candidate_id = db.scalar(
            select(CalendarEventReminder.id)
            .where(CalendarEventReminder.scheduled_for <= current)
            .where((CalendarEventReminder.status == "pending") | ((CalendarEventReminder.status == "processing") & (CalendarEventReminder.locked_until <= current)))
            .order_by(CalendarEventReminder.scheduled_for)
            .limit(1)
        )
        if candidate_id is None:
            break
        claim = db.execute(
            update(CalendarEventReminder)
            .where(CalendarEventReminder.id == candidate_id)
            .where((CalendarEventReminder.status == "pending") | ((CalendarEventReminder.status == "processing") & (CalendarEventReminder.locked_until <= current)))
            .values(status="processing", attempts=CalendarEventReminder.attempts + 1, locked_until=current + timedelta(minutes=2))
        )
        db.commit()
        if claim.rowcount != 1:
            continue
        reminder = db.get(CalendarEventReminder, candidate_id)
        if reminder is None:
            continue
        event = db.scalar(select(CalendarEvent).where(CalendarEvent.id == reminder.event_id, CalendarEvent.deleted_at.is_(None)))
        if event is None:
            reminder.status = "cancelled"
            reminder.locked_until = None
            db.commit()
            continue
        dedupe_key = f"event-reminder:{reminder.id}"
        existing = db.scalar(select(Notification.id).where(Notification.dedupe_key == dedupe_key))
        created_notification = None
        if existing is None:
            created_notification = Notification(user_id=reminder.user_id, type="event_reminder", title="Event reminder", body=event.title[:240], dedupe_key=dedupe_key)
            db.add(created_notification)
            db.flush()
        reminder.status = "delivered"
        reminder.delivered_at = current
        reminder.locked_until = None
        if created_notification is not None:
            enqueue_deliveries(db, created_notification)
        db.commit()
        delivered += 1
    return delivered
