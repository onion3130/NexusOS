"""Calendar-domain services with ownership, idempotency, and audit boundaries."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession, selectinload

from app.db.base import utc_now
from app.db.models import CalendarCategory, CalendarEvent, CalendarEventReminder, Job
from app.modules.calendar.schemas import CategoryCreate, EventCreate, EventReminderInput, EventUpdate
from app.modules.identity.service import add_audit_event


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _category(db: OrmSession, user_id: str, name: str | None, color: str | None = None) -> CalendarCategory | None:
    if not name:
        return None
    normalized = name.casefold()
    category = db.scalar(select(CalendarCategory).where(CalendarCategory.user_id == user_id, CalendarCategory.normalized_name == normalized))
    if category is None:
        category = CalendarCategory(user_id=user_id, name=name, normalized_name=normalized, color=color)
        db.add(category)
        db.flush()
    return category


def _load_event(db: OrmSession, user_id: str, event_id: str) -> CalendarEvent | None:
    return db.scalar(
        select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.user_id == user_id, CalendarEvent.deleted_at.is_(None)).options(
            selectinload(CalendarEvent.category), selectinload(CalendarEvent.reminders)
        )
    )


def _mutation_key(user_id: str, operation: str, key: str) -> str:
    return hashlib.sha256(f"{user_id}:{operation}:{key}".encode("utf-8")).hexdigest()


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _prior_mutation(db: OrmSession, user_id: str, operation: str, key: str | None, payload: object | None = None) -> tuple[str, str] | None:
    if not key:
        return None
    job = db.scalar(select(Job).where(Job.idempotency_key == _mutation_key(user_id, operation, key)))
    if not job or not job.payload_json:
        return None
    stored = json.loads(job.payload_json)
    stored_fingerprint = str(stored.get("fingerprint", ""))
    if payload is not None and stored_fingerprint and stored_fingerprint != _fingerprint(payload):
        raise ValueError("Idempotency-Key was already used for a different operation")
    return str(stored.get("resource_id")), stored_fingerprint


def _record_mutation(db: OrmSession, user_id: str, operation: str, key: str | None, resource_id: str, payload: object | None = None) -> None:
    if key:
        db.add(Job(job_type="mutation", status="completed", available_at=utc_now(), idempotency_key=_mutation_key(user_id, operation, key), payload_json=json.dumps({"resource_id": resource_id, "fingerprint": _fingerprint(payload) if payload is not None else ""}, separators=(",", ":")), completed_at=utc_now()))


def list_events(db: OrmSession, user_id: str, *, start_from: datetime | None = None, start_to: datetime | None = None, category: str | None = None, limit: int = 100, cursor: str | None = None) -> list[CalendarEvent]:
    """List only current-user events within an optional UTC range."""
    statement = select(CalendarEvent).where(CalendarEvent.user_id == user_id, CalendarEvent.deleted_at.is_(None)).options(selectinload(CalendarEvent.category), selectinload(CalendarEvent.reminders))
    if start_from is not None:
        statement = statement.where(CalendarEvent.starts_at >= start_from)
    if start_to is not None:
        statement = statement.where(CalendarEvent.starts_at <= start_to)
    if category:
        statement = statement.join(CalendarCategory).where(CalendarCategory.user_id == user_id, CalendarCategory.normalized_name == category.casefold())
    if cursor:
        statement = statement.where(CalendarEvent.id < cursor)
    return list(db.scalars(statement.order_by(CalendarEvent.starts_at, CalendarEvent.id).limit(max(1, min(limit, 200)))))


def get_event(db: OrmSession, user_id: str, event_id: str) -> CalendarEvent | None:
    return _load_event(db, user_id, event_id)


def create_event(db: OrmSession, user_id: str, payload: EventCreate, idempotency_key: str | None = None) -> CalendarEvent:
    """Create an event with optional reminders atomically."""
    prior = _prior_mutation(db, user_id, "event-create", idempotency_key, payload.model_dump(mode="json"))
    if prior:
        existing = _load_event(db, user_id, prior[0])
        if existing:
            return existing
    category = _category(db, user_id, payload.category)
    event = CalendarEvent(
        user_id=user_id,
        category_id=category.id if category else None,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        all_day=payload.all_day,
    )
    db.add(event)
    db.flush()
    _replace_reminders(db, user_id, event, payload.reminders)
    _record_mutation(db, user_id, "event-create", idempotency_key, event.id, payload.model_dump(mode="json"))
    add_audit_event(db, action="calendar.create", result="success", actor_user_id=user_id, target=event.id, metadata={"title": event.title})
    db.commit()
    return _load_event(db, user_id, event.id)  # type: ignore[return-value]


def update_event(db: OrmSession, user_id: str, event_id: str, payload: EventUpdate, idempotency_key: str | None = None) -> CalendarEvent | None:
    """Update an owned event and recalculate pending relative reminders."""
    mutation_payload = {"event_id": event_id, "changes": payload.model_dump(mode="json", exclude_unset=True)}
    prior = _prior_mutation(db, user_id, "event-update", idempotency_key, mutation_payload)
    if prior:
        return _load_event(db, user_id, prior[0])
    event = _load_event(db, user_id, event_id)
    if event is None:
        return None
    values = payload.model_dump(exclude_unset=True)
    category_name = values.pop("category", None)
    for key, value in values.items():
        setattr(event, key, value)
    if category_name is not None:
        category = _category(db, user_id, category_name)
        event.category_id = category.id if category else None
    if "starts_at" in values:
        for reminder in event.reminders:
            if reminder.status == "pending" and reminder.offset_minutes is not None and event.starts_at is not None:
                reminder.scheduled_for = _aware(event.starts_at) - timedelta(minutes=reminder.offset_minutes)
    if "ends_at" in values and event.ends_at < event.starts_at:
        raise ValueError("ends_at must not be before starts_at")
    _record_mutation(db, user_id, "event-update", idempotency_key, event.id, mutation_payload)
    add_audit_event(db, action="calendar.update", result="success", actor_user_id=user_id, target=event.id, metadata={"fields": sorted(values)})
    db.commit()
    return _load_event(db, user_id, event.id)


def delete_event(db: OrmSession, user_id: str, event_id: str, idempotency_key: str | None = None) -> CalendarEvent | None:
    """Soft-delete an owned event and cancel its reminders."""
    prior = _prior_mutation(db, user_id, "event-delete", idempotency_key, {"event_id": event_id})
    if prior:
        return db.scalar(select(CalendarEvent).where(CalendarEvent.id == prior[0], CalendarEvent.user_id == user_id))
    event = _load_event(db, user_id, event_id)
    if event is None:
        return None
    event.deleted_at = utc_now()
    for reminder in event.reminders:
        reminder.status = "cancelled"
    _record_mutation(db, user_id, "event-delete", idempotency_key, event.id, {"event_id": event_id})
    add_audit_event(db, action="calendar.delete", result="success", actor_user_id=user_id, target=event.id)
    db.commit()
    return event


def _replace_reminders(db: OrmSession, user_id: str, event: CalendarEvent, inputs: list[EventReminderInput]) -> None:
    for reminder in event.reminders:
        if reminder.status == "pending":
            reminder.status = "cancelled"
    for item in inputs:
        scheduled = item.scheduled_for
        if item.offset_minutes is not None:
            scheduled = _aware(event.starts_at) - timedelta(minutes=item.offset_minutes)
        if scheduled is None:
            raise ValueError("reminder schedule is required")
        db.add(CalendarEventReminder(user_id=user_id, event_id=event.id, scheduled_for=scheduled, offset_minutes=item.offset_minutes, status="pending"))


def add_reminder(db: OrmSession, user_id: str, event_id: str, item: EventReminderInput, idempotency_key: str | None = None) -> CalendarEvent | None:
    """Add one reminder to an owned event."""
    mutation_payload = {"event_id": event_id, "reminder": item.model_dump(mode="json")}
    prior = _prior_mutation(db, user_id, "event-reminder-create", idempotency_key, mutation_payload)
    if prior:
        reminder = db.get(CalendarEventReminder, prior[0])
        if reminder is not None:
            return _load_event(db, user_id, reminder.event_id)
    event = _load_event(db, user_id, event_id)
    if event is None:
        return None
    scheduled = item.scheduled_for
    if item.offset_minutes is not None:
        scheduled = _aware(event.starts_at) - timedelta(minutes=item.offset_minutes)
    if scheduled is None:
        raise ValueError("reminder schedule is required")
    reminder = CalendarEventReminder(user_id=user_id, event_id=event.id, scheduled_for=scheduled, offset_minutes=item.offset_minutes, status="pending")
    event.reminders.append(reminder)
    db.add(reminder)
    db.flush()
    _record_mutation(db, user_id, "event-reminder-create", idempotency_key, reminder.id, mutation_payload)
    add_audit_event(db, action="calendar.reminder_create", result="success", actor_user_id=user_id, target=event.id)
    db.commit()
    return _load_event(db, user_id, event.id)


def update_reminder(db: OrmSession, user_id: str, reminder_id: str, item: EventReminderInput, idempotency_key: str | None = None) -> CalendarEvent | None:
    mutation_payload = {"reminder_id": reminder_id, "reminder": item.model_dump(mode="json")}
    prior = _prior_mutation(db, user_id, "event-reminder-update", idempotency_key, mutation_payload)
    if prior:
        prior_reminder = db.get(CalendarEventReminder, prior[0])
        if prior_reminder is not None:
            return _load_event(db, user_id, prior_reminder.event_id)
    reminder = db.scalar(select(CalendarEventReminder).where(CalendarEventReminder.id == reminder_id, CalendarEventReminder.user_id == user_id))
    if reminder is None:
        return None
    event = _load_event(db, user_id, reminder.event_id)
    if event is None:
        return None
    scheduled = item.scheduled_for
    if item.offset_minutes is not None:
        scheduled = _aware(event.starts_at) - timedelta(minutes=item.offset_minutes)
    reminder.scheduled_for = scheduled
    reminder.offset_minutes = item.offset_minutes
    reminder.status = "pending"
    reminder.delivered_at = None
    reminder.locked_until = None
    _record_mutation(db, user_id, "event-reminder-update", idempotency_key, reminder.id, mutation_payload)
    add_audit_event(db, action="calendar.reminder_update", result="success", actor_user_id=user_id, target=reminder.id)
    db.commit()
    return _load_event(db, user_id, event.id)


def delete_reminder(db: OrmSession, user_id: str, reminder_id: str, idempotency_key: str | None = None) -> bool:
    """Cancel one owned event reminder idempotently."""
    prior = _prior_mutation(db, user_id, "event-reminder-delete", idempotency_key, {"reminder_id": reminder_id})
    if prior:
        return db.get(CalendarEventReminder, prior[0]) is not None
    reminder = db.scalar(select(CalendarEventReminder).where(CalendarEventReminder.id == reminder_id, CalendarEventReminder.user_id == user_id))
    if reminder is None:
        return False
    reminder.status = "cancelled"
    _record_mutation(db, user_id, "event-reminder-delete", idempotency_key, reminder.id, {"reminder_id": reminder_id})
    add_audit_event(db, action="calendar.reminder_delete", result="success", actor_user_id=user_id, target=reminder.id)
    db.commit()
    return True


def list_categories(db: OrmSession, user_id: str) -> list[CalendarCategory]:
    return list(db.scalars(select(CalendarCategory).where(CalendarCategory.user_id == user_id).order_by(CalendarCategory.name)))


def create_category(db: OrmSession, user_id: str, payload: CategoryCreate, idempotency_key: str | None = None) -> CalendarCategory:
    prior = _prior_mutation(db, user_id, "calendar-category-create", idempotency_key, payload.model_dump(mode="json"))
    if prior:
        existing = db.get(CalendarCategory, prior[0])
        if existing is not None:
            return existing
    category = _category(db, user_id, payload.name, payload.color)
    if category is None:
        raise ValueError("category name is required")
    _record_mutation(db, user_id, "calendar-category-create", idempotency_key, category.id, payload.model_dump(mode="json"))
    db.commit()
    return category


def delete_category(db: OrmSession, user_id: str, category_id: str, idempotency_key: str | None = None) -> bool:
    prior = _prior_mutation(db, user_id, "calendar-category-delete", idempotency_key, {"category_id": category_id})
    if prior:
        return True
    category = db.scalar(select(CalendarCategory).where(CalendarCategory.id == category_id, CalendarCategory.user_id == user_id))
    if category is None:
        return False
    db.delete(category)
    _record_mutation(db, user_id, "calendar-category-delete", idempotency_key, category_id, {"category_id": category_id})
    add_audit_event(db, action="calendar.category_delete", result="success", actor_user_id=user_id, target=category_id)
    db.commit()
    return True
