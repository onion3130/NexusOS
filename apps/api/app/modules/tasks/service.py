"""Task-domain services with ownership, recurrence, and audit boundaries."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession, selectinload

from app.db.base import utc_now
from app.db.models import Job, Notification, Reminder, Tag, Task, TaskCategory, TaskSeries
from app.modules.identity.service import add_audit_event
from app.modules.tasks.recurrence import next_occurrence, validate_rule
from app.modules.tasks.schemas import CategoryCreate, ReminderInput, TaskCreate, TaskUpdate, TagCreate


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _category(db: OrmSession, user_id: str, name: str | None, color: str | None = None) -> TaskCategory | None:
    if not name:
        return None
    normalized = name.casefold()
    category = db.scalar(select(TaskCategory).where(TaskCategory.user_id == user_id, TaskCategory.normalized_name == normalized))
    if category is None:
        category = TaskCategory(user_id=user_id, name=name, normalized_name=normalized, color=color)
        db.add(category)
        db.flush()
    return category


def _tags(db: OrmSession, user_id: str, names: list[str]) -> list[Tag]:
    result: list[Tag] = []
    for name in names:
        normalized = name.casefold()
        tag = db.scalar(select(Tag).where(Tag.user_id == user_id, Tag.normalized_name == normalized))
        if tag is None:
            tag = Tag(user_id=user_id, name=name, normalized_name=normalized)
            db.add(tag)
            db.flush()
        result.append(tag)
    return result


def _load_task(db: OrmSession, user_id: str, task_id: str) -> Task | None:
    return db.scalar(
        select(Task).where(Task.id == task_id, Task.user_id == user_id, Task.deleted_at.is_(None)).options(
            selectinload(Task.category), selectinload(Task.tags), selectinload(Task.series), selectinload(Task.reminders)
        )
    )


def list_tasks(db: OrmSession, user_id: str, *, status: str | None = None, priority: str | None = None, category: str | None = None, tag: str | None = None, include_completed: bool = False, limit: int = 50, cursor: str | None = None) -> list[Task]:
    """List only current-user tasks with bounded filters."""
    statement = select(Task).where(Task.user_id == user_id, Task.deleted_at.is_(None)).options(selectinload(Task.category), selectinload(Task.tags), selectinload(Task.series), selectinload(Task.reminders))
    if status:
        statement = statement.where(Task.status == status)
    elif not include_completed:
        statement = statement.where(Task.status != "completed")
    if priority:
        statement = statement.where(Task.priority == priority)
    if category:
        statement = statement.join(TaskCategory).where(TaskCategory.user_id == user_id, TaskCategory.normalized_name == category.casefold())
    if tag:
        statement = statement.join(Task.tags).where(Tag.user_id == user_id, Tag.normalized_name == tag.casefold())
    if cursor:
        statement = statement.where(Task.id < cursor)
    return list(db.scalars(statement.order_by(Task.due_at.is_(None), Task.due_at, Task.updated_at.desc()).limit(max(1, min(limit, 100)))) )


def get_task(db: OrmSession, user_id: str, task_id: str) -> Task | None:
    """Resolve a live task inside the current user's ownership boundary."""
    return _load_task(db, user_id, task_id)


def _mutation_key(user_id: str, operation: str, key: str) -> str:
    """Return a bounded, user-scoped idempotency key for SQLite/PostgreSQL."""
    return hashlib.sha256(f"{user_id}:{operation}:{key}".encode("utf-8")).hexdigest()


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


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _record_mutation(db: OrmSession, user_id: str, operation: str, key: str | None, resource_id: str, payload: object | None = None) -> None:
    if key:
        db.add(Job(job_type="mutation", status="completed", available_at=utc_now(), idempotency_key=_mutation_key(user_id, operation, key), payload_json=json.dumps({"resource_id": resource_id, "fingerprint": _fingerprint(payload) if payload is not None else ""}, separators=(",", ":")), completed_at=utc_now()))


def create_task(db: OrmSession, user_id: str, payload: TaskCreate, idempotency_key: str | None = None) -> Task:
    """Create a task, optional recurrence series, and reminders atomically."""
    prior = _prior_mutation(db, user_id, "task-create", idempotency_key, payload.model_dump(mode="json"))
    if prior:
        existing = _load_task(db, user_id, prior[0])
        if existing:
            return existing
    recurrence = validate_rule(payload.recurrence) if payload.recurrence else None
    category = _category(db, user_id, payload.category)
    series = None
    if recurrence:
        series = TaskSeries(user_id=user_id, recurrence_json=json.dumps(recurrence, separators=(",", ":")), timezone=str(recurrence.get("timezone", "UTC")))
        db.add(series)
        db.flush()
    task = Task(user_id=user_id, series_id=series.id if series else None, category_id=category.id if category else None, title=payload.title, description=payload.description, due_at=payload.due_at, priority=payload.priority, status=payload.status)
    task.tags = _tags(db, user_id, payload.tags)
    db.add(task)
    db.flush()
    _replace_reminders(db, user_id, task, payload.reminders)
    _record_mutation(db, user_id, "task-create", idempotency_key, task.id, payload.model_dump(mode="json"))
    add_audit_event(db, action="tasks.create", result="success", actor_user_id=user_id, target=task.id, metadata={"priority": task.priority})
    db.commit()
    return _load_task(db, user_id, task.id)  # type: ignore[return-value]


def update_task(db: OrmSession, user_id: str, task_id: str, payload: TaskUpdate, idempotency_key: str | None = None) -> Task | None:
    """Update an owned task and safely replace its mutable classification."""
    mutation_payload = {"task_id": task_id, "changes": payload.model_dump(mode="json", exclude_unset=True)}
    prior = _prior_mutation(db, user_id, "task-update", idempotency_key, mutation_payload)
    if prior:
        return _load_task(db, user_id, prior[0])
    task = _load_task(db, user_id, task_id)
    if task is None:
        return None
    values = payload.model_dump(exclude_unset=True)
    requested_status = values.get("status")
    if requested_status == "in_progress" and task.status == "completed":
        raise ValueError("completed tasks must be reopened through a dedicated action")
    recurrence = values.pop("recurrence", None)
    tags = values.pop("tags", None)
    category_name = values.pop("category", None)
    for key, value in values.items():
        setattr(task, key, value)
    if "status" in values and values["status"] == "completed":
        task.completed_at = utc_now()
    if category_name is not None:
        category = _category(db, user_id, category_name)
        task.category_id = category.id if category else None
    if tags is not None:
        task.tags = _tags(db, user_id, tags)
    if recurrence is not None:
        normalized = validate_rule(recurrence)
        if task.series is None:
            task.series = TaskSeries(user_id=user_id, recurrence_json=json.dumps(normalized, separators=(",", ":")), timezone=str(normalized.get("timezone", "UTC")))
        else:
            task.series.recurrence_json = json.dumps(normalized, separators=(",", ":"))
            task.series.active = True
    if "due_at" in values:
        for reminder in task.reminders:
            if reminder.status == "pending" and reminder.offset_minutes is not None and task.due_at is not None:
                reminder.scheduled_for = _aware(task.due_at) - timedelta(minutes=reminder.offset_minutes)
    if task.status in {"completed", "archived"}:
        for reminder in task.reminders:
            if reminder.status in {"pending", "processing"}:
                reminder.status = "cancelled"
    _record_mutation(db, user_id, "task-update", idempotency_key, task.id, mutation_payload)
    add_audit_event(db, action="tasks.update", result="success", actor_user_id=user_id, target=task.id, metadata={"fields": sorted(values)})
    db.commit()
    return _load_task(db, user_id, task.id)


def complete_task(db: OrmSession, user_id: str, task_id: str, idempotency_key: str | None = None) -> tuple[Task | None, Task | None]:
    """Complete an occurrence and create one next recurring occurrence."""
    prior = _prior_mutation(db, user_id, "task-complete", idempotency_key, {"task_id": task_id})
    if prior:
        return _load_task(db, user_id, prior[0]), None
    task = _load_task(db, user_id, task_id)
    if task is None:
        return None, None
    task.status = "completed"
    task.completed_at = utc_now()
    for reminder in task.reminders:
        if reminder.status in {"pending", "processing"}:
            reminder.status = "cancelled"
    next_task = None
    if task.series and task.series.active and task.due_at:
        rule = json.loads(task.series.recurrence_json)
        occurrence_count = db.scalar(select(func.count(Task.id)).where(Task.series_id == task.series_id, Task.status == "completed")) or 0
        due_at = next_occurrence(_aware(task.due_at), rule, next_index=occurrence_count + 1)
        if due_at:
            next_task = Task(user_id=user_id, series_id=task.series.id, category_id=task.category_id, title=task.title, description=task.description, due_at=due_at, priority=task.priority, status="open", tags=list(task.tags))
            db.add(next_task)
            db.flush()
    _record_mutation(db, user_id, "task-complete", idempotency_key, task.id, {"task_id": task_id})
    add_audit_event(db, action="tasks.complete", result="success", actor_user_id=user_id, target=task.id, metadata={"next_task": next_task.id if next_task else None})
    db.commit()
    return _load_task(db, user_id, task.id), (_load_task(db, user_id, next_task.id) if next_task else None)


def delete_task(db: OrmSession, user_id: str, task_id: str, idempotency_key: str | None = None) -> Task | None:
    """Soft-delete an owned task and cancel its reminders."""
    prior = _prior_mutation(db, user_id, "task-delete", idempotency_key, {"task_id": task_id})
    if prior:
        return db.scalar(select(Task).where(Task.id == prior[0], Task.user_id == user_id))
    task = _load_task(db, user_id, task_id)
    if task is None:
        return None
    task.deleted_at = utc_now()
    if task.series:
        task.series.active = False
    for reminder in task.reminders:
        reminder.status = "cancelled"
    _record_mutation(db, user_id, "task-delete", idempotency_key, task.id, {"task_id": task_id})
    add_audit_event(db, action="tasks.delete", result="success", actor_user_id=user_id, target=task.id)
    db.commit()
    return task


def _replace_reminders(db: OrmSession, user_id: str, task: Task, inputs: list[ReminderInput]) -> None:
    for reminder in task.reminders:
        if reminder.status == "pending":
            reminder.status = "cancelled"
    for item in inputs:
        scheduled = item.scheduled_for
        if item.offset_minutes is not None:
            if task.due_at is None:
                raise ValueError("relative reminders require a due date")
            scheduled = _aware(task.due_at) - timedelta(minutes=item.offset_minutes)
        if scheduled is None:
            raise ValueError("reminder schedule is required")
        db.add(Reminder(user_id=user_id, task_id=task.id, scheduled_for=scheduled, offset_minutes=item.offset_minutes, status="pending"))


def add_reminder(db: OrmSession, user_id: str, task_id: str, item: ReminderInput, idempotency_key: str | None = None) -> Task | None:
    """Add one reminder to an owned task without changing existing reminders."""
    mutation_payload = {"task_id": task_id, "reminder": item.model_dump(mode="json")}
    prior = _prior_mutation(db, user_id, "reminder-create", idempotency_key, mutation_payload)
    if prior:
        reminder = db.get(Reminder, prior[0])
        if reminder is not None:
            return _load_task(db, user_id, reminder.task_id)
    task = _load_task(db, user_id, task_id)
    if task is None:
        return None
    scheduled = item.scheduled_for
    if item.offset_minutes is not None:
        if task.due_at is None:
            raise ValueError("relative reminders require a due date")
        scheduled = _aware(task.due_at) - timedelta(minutes=item.offset_minutes)
    if scheduled is None:
        raise ValueError("reminder schedule is required")
    reminder = Reminder(user_id=user_id, task_id=task.id, scheduled_for=scheduled, offset_minutes=item.offset_minutes, status="pending")
    task.reminders.append(reminder)
    db.add(reminder)
    db.flush()
    _record_mutation(db, user_id, "reminder-create", idempotency_key, reminder.id, mutation_payload)
    add_audit_event(db, action="tasks.reminder_create", result="success", actor_user_id=user_id, target=task.id)
    db.commit()
    return _load_task(db, user_id, task.id)


def update_reminder(db: OrmSession, user_id: str, reminder_id: str, item: ReminderInput, idempotency_key: str | None = None) -> Task | None:
    mutation_payload = {"reminder_id": reminder_id, "reminder": item.model_dump(mode="json")}
    prior = _prior_mutation(db, user_id, "reminder-update", idempotency_key, mutation_payload)
    if prior:
        prior_reminder = db.get(Reminder, prior[0])
        if prior_reminder is not None:
            return _load_task(db, user_id, prior_reminder.task_id)
    reminder = db.scalar(select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id))
    if reminder is None:
        return None
    task = _load_task(db, user_id, reminder.task_id)
    if task is None:
        return None
    scheduled = item.scheduled_for
    if item.offset_minutes is not None:
        if task.due_at is None:
            raise ValueError("relative reminders require a due date")
        scheduled = _aware(task.due_at) - timedelta(minutes=item.offset_minutes)
    reminder.scheduled_for = scheduled
    reminder.offset_minutes = item.offset_minutes
    reminder.status = "pending"
    reminder.delivered_at = None
    reminder.locked_until = None
    _record_mutation(db, user_id, "reminder-update", idempotency_key, reminder.id, mutation_payload)
    add_audit_event(db, action="tasks.reminder_update", result="success", actor_user_id=user_id, target=reminder.id)
    db.commit()
    return _load_task(db, user_id, task.id)


def delete_reminder(db: OrmSession, user_id: str, reminder_id: str, idempotency_key: str | None = None) -> bool:
    """Cancel one owned reminder idempotently."""
    prior = _prior_mutation(db, user_id, "reminder-delete", idempotency_key, {"reminder_id": reminder_id})
    if prior:
        return db.get(Reminder, prior[0]) is not None
    reminder = db.scalar(select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id))
    if reminder is None:
        return False
    reminder.status = "cancelled"
    _record_mutation(db, user_id, "reminder-delete", idempotency_key, reminder.id, {"reminder_id": reminder_id})
    add_audit_event(db, action="tasks.reminder_delete", result="success", actor_user_id=user_id, target=reminder.id)
    db.commit()
    return True


def list_categories(db: OrmSession, user_id: str) -> list[TaskCategory]:
    return list(db.scalars(select(TaskCategory).where(TaskCategory.user_id == user_id).order_by(TaskCategory.name)))


def create_category(db: OrmSession, user_id: str, payload: CategoryCreate, idempotency_key: str | None = None) -> TaskCategory:
    """Create or replay a user-owned category mutation."""
    prior = _prior_mutation(db, user_id, "category-create", idempotency_key, payload.model_dump(mode="json"))
    if prior:
        existing = db.get(TaskCategory, prior[0])
        if existing is not None:
            return existing
    category = _category(db, user_id, payload.name, payload.color)
    if category is None:
        raise ValueError("category name is required")
    _record_mutation(db, user_id, "category-create", idempotency_key, category.id, payload.model_dump(mode="json"))
    db.commit()
    return category


def delete_category(db: OrmSession, user_id: str, category_id: str, idempotency_key: str | None = None) -> bool:
    """Delete a user-owned category idempotently."""
    prior = _prior_mutation(db, user_id, "category-delete", idempotency_key, {"category_id": category_id})
    if prior:
        return True
    category = db.scalar(select(TaskCategory).where(TaskCategory.id == category_id, TaskCategory.user_id == user_id))
    if category is None:
        return False
    db.delete(category)
    _record_mutation(db, user_id, "category-delete", idempotency_key, category_id, {"category_id": category_id})
    add_audit_event(db, action="tasks.category_delete", result="success", actor_user_id=user_id, target=category_id)
    db.commit()
    return True


def list_tags(db: OrmSession, user_id: str) -> list[Tag]:
    return list(db.scalars(select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)))


def create_tag(db: OrmSession, user_id: str, payload: TagCreate, idempotency_key: str | None = None) -> Tag:
    """Create or replay a user-owned tag mutation."""
    prior = _prior_mutation(db, user_id, "tag-create", idempotency_key, payload.model_dump(mode="json"))
    if prior:
        existing = db.get(Tag, prior[0])
        if existing is not None:
            return existing
    tags = _tags(db, user_id, [payload.name])
    _record_mutation(db, user_id, "tag-create", idempotency_key, tags[0].id, payload.model_dump(mode="json"))
    db.commit()
    return tags[0]


def delete_tag(db: OrmSession, user_id: str, tag_id: str, idempotency_key: str | None = None) -> bool:
    """Delete a user-owned tag idempotently."""
    prior = _prior_mutation(db, user_id, "tag-delete", idempotency_key, {"tag_id": tag_id})
    if prior:
        return True
    tag = db.scalar(select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id))
    if tag is None:
        return False
    db.delete(tag)
    _record_mutation(db, user_id, "tag-delete", idempotency_key, tag_id, {"tag_id": tag_id})
    add_audit_event(db, action="tasks.tag_delete", result="success", actor_user_id=user_id, target=tag_id)
    db.commit()
    return True


def list_notifications(db: OrmSession, user_id: str, unread_only: bool = False, limit: int = 50) -> tuple[list[Notification], int]:
    statement = select(Notification).where(Notification.user_id == user_id, Notification.dismissed_at.is_(None))
    if unread_only:
        statement = statement.where(Notification.read_at.is_(None))
    items = list(db.scalars(statement.order_by(Notification.created_at.desc()).limit(max(1, min(limit, 100)))))
    count = db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user_id, Notification.read_at.is_(None), Notification.dismissed_at.is_(None))) or 0
    return items, count


def mark_notification_read(db: OrmSession, user_id: str, notification_id: str, idempotency_key: str | None = None) -> bool:
    """Mark one owned notification read idempotently."""
    prior = _prior_mutation(db, user_id, "notification-read", idempotency_key, {"notification_id": notification_id})
    if prior:
        return True
    notification = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id))
    if notification is None:
        return False
    notification.read_at = utc_now()
    _record_mutation(db, user_id, "notification-read", idempotency_key, notification.id, {"notification_id": notification_id})
    db.commit()
    return True


def mark_all_notifications_read(db: OrmSession, user_id: str, idempotency_key: str | None = None) -> int:
    """Mark all owned notifications read idempotently."""
    if _prior_mutation(db, user_id, "notification-read-all", idempotency_key, {"resource_id": "all"}):
        return 0
    items = db.scalars(select(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))).all()
    now = utc_now()
    for item in items:
        item.read_at = now
    _record_mutation(db, user_id, "notification-read-all", idempotency_key, "all", {"resource_id": "all"})
    db.commit()
    return len(items)
