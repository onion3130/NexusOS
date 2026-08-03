"""Milestone 6 task, reminder, notification, and safety tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.models import Notification, Reminder, Task as TaskModel, TaskCategory, User
from app.db.session import get_session_factory
from app.modules.assistant.schemas import ProposedToolCall, ToolValidationError
from app.modules.assistant.service import approve_tool_call
from app.modules.assistant.tools.registry import ToolRegistry
from app.modules.identity.service import bootstrap_owner
from app.modules.system.service import SystemService
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import create_task
from app.modules.tasks.worker import process_due_reminders


def _bootstrap_owner() -> None:
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()


def _login(client) -> None:
    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200


def test_task_crud_requires_auth_and_csrf(client) -> None:
    """Task reads require auth and cookie mutations require CSRF."""
    assert client.get("/api/v1/tasks").status_code == 401
    _bootstrap_owner()
    _login(client)
    blocked = client.post("/api/v1/tasks", json={"title": "Buy milk"})
    assert blocked.status_code == 403
    csrf = client.cookies.get("nexus_csrf")
    created = client.post("/api/v1/tasks", json={"title": "Buy milk", "priority": "high", "tags": ["home"]}, headers={"X-CSRF-Token": csrf, "Idempotency-Key": "create-1"})
    assert created.status_code == 201
    replay = client.post("/api/v1/tasks", json={"title": "Different title"}, headers={"X-CSRF-Token": csrf, "Idempotency-Key": "create-1"})
    assert replay.status_code == 422
    assert replay.json()["detail"] == "Idempotency-Key was already used for a different operation"
    task_id = created.json()["id"]
    updated = client.patch(f"/api/v1/tasks/{task_id}", json={"status": "in_progress"}, headers={"X-CSRF-Token": csrf, "Idempotency-Key": "update-1"})
    assert updated.status_code == 200
    completed = client.post(f"/api/v1/tasks/{task_id}/complete", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "complete-1"})
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    delete_headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "delete-1"}
    deleted = client.delete(f"/api/v1/tasks/{task_id}", headers=delete_headers)
    replay_deleted = client.delete(f"/api/v1/tasks/{task_id}", headers=delete_headers)
    assert deleted.status_code == replay_deleted.status_code == 204
    assert client.get(f"/api/v1/tasks/{task_id}").status_code == 404


def test_notification_read_all_route_and_idempotency(client) -> None:
    """Notification read state is authenticated, CSRF-protected, and replay-safe."""
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    db.add(Notification(user_id=user.id, type="task_reminder", title="One", body="First", dedupe_key="test:one"))
    db.add(Notification(user_id=user.id, type="task_reminder", title="Two", body="Second", dedupe_key="test:two"))
    db.commit()
    db.close()
    response = client.post("/api/v1/notifications/read-all", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "read-all-1"})
    assert response.status_code == 204
    replay = client.post("/api/v1/notifications/read-all", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "read-all-1"})
    assert replay.status_code == 204
    assert client.get("/api/v1/notifications?unread_only=true").json()["unread_count"] == 0


def test_recurring_task_creates_next_occurrence(client) -> None:
    """Completing a recurring task preserves history and creates one future occurrence."""
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    due_at = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    created = client.post("/api/v1/tasks", json={"title": "Daily review", "due_at": due_at, "recurrence": {"version": 1, "frequency": "daily", "interval": 1}}, headers={"X-CSRF-Token": csrf})
    assert created.status_code == 201
    response = client.post(f"/api/v1/tasks/{created.json()['id']}/complete", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    listing = client.get("/api/v1/tasks").json()["items"]
    assert any(item["title"] == "Daily review" and item["status"] == "open" for item in listing)


def test_worker_delivers_due_reminder_once(configured_app) -> None:
    """Due reminders create one persistent notification and remain delivered on replay."""
    _bootstrap_owner()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    task = TaskModel(user_id=user.id, title="Reminder", status="open", priority="normal")
    db.add(task)
    db.flush()
    reminder = Reminder(user_id=user.id, task_id=task.id, scheduled_for=datetime.now(UTC) - timedelta(minutes=1), status="pending")
    db.add(reminder)
    db.commit()
    assert process_due_reminders(db, now=datetime.now(UTC)) == 1
    assert process_due_reminders(db, now=datetime.now(UTC)) == 0
    assert db.query(Notification).count() == 1
    db.close()


def test_reminder_mutation_idempotency(client) -> None:
    """Reminder creation replays the same task response without duplication."""
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    due_at = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    created = client.post("/api/v1/tasks", json={"title": "Reminder target", "due_at": due_at}, headers={"X-CSRF-Token": csrf})
    assert created.status_code == 201
    task_id = created.json()["id"]
    headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "reminder-create-1"}
    first = client.post(f"/api/v1/tasks/{task_id}/reminders", json={"offset_minutes": 15}, headers=headers)
    replay = client.post(f"/api/v1/tasks/{task_id}/reminders", json={"offset_minutes": 15}, headers=headers)
    conflict = client.post(f"/api/v1/tasks/{task_id}/reminders", json={"offset_minutes": 30}, headers=headers)
    assert first.status_code == replay.status_code == 200
    assert conflict.status_code == 422
    assert len(first.json()["reminders"]) == len(replay.json()["reminders"]) == 1


def test_recurrence_rejects_unbounded_rule() -> None:
    """The recurrence boundary accepts only the documented bounded shape."""
    with pytest.raises(ValueError):
        TaskCreate(title="Bad", recurrence={"frequency": "yearly"})
    with pytest.raises(ValueError):
        TaskCreate(title="Bad timezone", recurrence={"frequency": "daily", "timezone": "not/a-timezone"})
    with pytest.raises(ValueError):
        TaskCreate(title="Bad count", recurrence={"frequency": "daily", "count": 10001})


def test_recurrence_count_stops_generation() -> None:
    """A finite recurrence does not create an occurrence after its count."""
    from app.modules.tasks.recurrence import next_occurrence
    current = datetime(2026, 1, 1, tzinfo=UTC)
    rule = {"frequency": "daily", "count": 2}
    assert next_occurrence(current, rule, next_index=1) is not None
    assert next_occurrence(current, rule, next_index=2) is not None
    assert next_occurrence(current, rule, next_index=3) is None


def test_task_tool_writes_require_confirmation(tmp_path) -> None:
    """Assistant task mutations are advertised as confirmation-gated."""
    registry = ToolRegistry(SystemService(tmp_path, tmp_path / "proc", tmp_path / "sys"))
    assert registry.requires_confirmation("tasks.create") is True
    assert registry.requires_confirmation("tasks.delete") is True
    with pytest.raises(ToolValidationError):
        registry.execute(ProposedToolCall(provider_id="x", tool_key="tasks.create", arguments={"title": "No DB"}), {"tasks.write"})


def test_category_and_tag_mutation_replay(client) -> None:
    """Category and tag mutations are replay-safe with idempotency keys."""
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "category-1"}
    category = client.post("/api/v1/task-categories", json={"name": "Home"}, headers=headers)
    replay_category = client.post("/api/v1/task-categories", json={"name": "Other"}, headers=headers)
    assert category.status_code == 201
    assert replay_category.status_code == 422
    assert replay_category.json()["detail"] == "Idempotency-Key was already used for a different operation"
    tag_headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "tag-1"}
    tag = client.post("/api/v1/tags", json={"name": "urgent"}, headers=tag_headers)
    replay_tag = client.post("/api/v1/tags", json={"name": "other"}, headers=tag_headers)
    assert tag.status_code == 201
    assert replay_tag.status_code == 422
    assert replay_tag.json()["detail"] == "Idempotency-Key was already used for a different operation"


def test_worker_reclaims_expired_processing_reminder(configured_app) -> None:
    """An expired worker lease is eligible for delivery again."""
    _bootstrap_owner()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    task = TaskModel(user_id=user.id, title="Lease recovery", status="open", priority="normal")
    db.add(task)
    db.flush()
    reminder = Reminder(user_id=user.id, task_id=task.id, scheduled_for=datetime.now(UTC) - timedelta(minutes=2), status="processing", locked_until=datetime.now(UTC) - timedelta(minutes=1))
    db.add(reminder)
    db.commit()
    assert process_due_reminders(db, now=datetime.now(UTC)) == 1
    assert db.query(Notification).count() == 1
    db.close()
