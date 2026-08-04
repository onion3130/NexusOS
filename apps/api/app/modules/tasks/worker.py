"""Bounded SQLite reminder processing for the NexusOS worker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session as OrmSession

from app.db.base import utc_now
from app.db.models import Notification, Reminder, Task
from app.modules.notifications.service import enqueue_deliveries


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def process_due_reminders(db: OrmSession, *, now: datetime | None = None, batch_size: int = 50) -> int:
    """Atomically claim and deliver one bounded batch of due reminders."""
    current = (now or utc_now()).astimezone(UTC)
    delivered = 0
    for _ in range(max(1, min(batch_size, 200))):
        candidate_id = db.scalar(
            select(Reminder.id)
            .where(Reminder.scheduled_for <= current)
            .where((Reminder.status == "pending") | ((Reminder.status == "processing") & (Reminder.locked_until <= current)))
            .order_by(Reminder.scheduled_for)
            .limit(1)
        )
        if candidate_id is None:
            break
        claim = db.execute(
            update(Reminder)
            .where(Reminder.id == candidate_id)
            .where((Reminder.status == "pending") | ((Reminder.status == "processing") & (Reminder.locked_until <= current)))
            .values(status="processing", attempts=Reminder.attempts + 1, locked_until=current + timedelta(minutes=2))
        )
        db.commit()
        if claim.rowcount != 1:
            continue
        reminder = db.get(Reminder, candidate_id)
        if reminder is None:
            continue
        task = db.scalar(select(Task).where(Task.id == reminder.task_id, Task.deleted_at.is_(None)))
        if task is None or task.status in {"completed", "archived"}:
            reminder.status = "cancelled"
            reminder.locked_until = None
            db.commit()
            continue
        dedupe_key = f"reminder:{reminder.id}"
        existing = db.scalar(select(Notification.id).where(Notification.dedupe_key == dedupe_key))
        created_notification = None
        if existing is None:
            created_notification = Notification(user_id=reminder.user_id, type="task_reminder", title="Task reminder", body=task.title[:240], task_id=task.id, reminder_id=reminder.id, dedupe_key=dedupe_key)
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
