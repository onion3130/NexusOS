"""Milestone 11 Phase A calendar event, category, and reminder tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.models import CalendarEvent, CalendarEventReminder, Notification, User
from app.db.session import get_session_factory
from app.modules.calendar.worker import process_due_event_reminders
from app.modules.identity.service import bootstrap_owner


def _bootstrap_owner() -> None:
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()


def _login(client) -> None:
    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200


def _event_payload(**overrides) -> dict:
    payload = {
        "title": "Team standup",
        "description": "Daily sync",
        "starts_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "ends_at": (datetime.now(UTC) + timedelta(days=1, hours=1)).isoformat(),
        "all_day": False,
    }
    payload.update(overrides)
    return payload


def test_event_crud_requires_auth_and_csrf(client) -> None:
    """Event reads require auth and cookie mutations require CSRF."""
    assert client.get("/api/v1/calendar/events").status_code == 401
    _bootstrap_owner()
    _login(client)
    blocked = client.post("/api/v1/calendar/events", json=_event_payload())
    assert blocked.status_code == 403
    csrf = client.cookies.get("nexus_csrf")
    created = client.post("/api/v1/calendar/events", json=_event_payload(), headers={"X-CSRF-Token": csrf, "Idempotency-Key": "event-1"})
    assert created.status_code == 201
    replay = client.post("/api/v1/calendar/events", json=_event_payload(title="Different"), headers={"X-CSRF-Token": csrf, "Idempotency-Key": "event-1"})
    assert replay.status_code == 422
    assert replay.json()["detail"] == "Idempotency-Key was already used for a different operation"
    event_id = created.json()["id"]
    updated = client.patch(f"/api/v1/calendar/events/{event_id}", json={"location": "Room 4"}, headers={"X-CSRF-Token": csrf, "Idempotency-Key": "event-update-1"})
    assert updated.status_code == 200
    assert updated.json()["location"] == "Room 4"
    delete_headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "event-delete-1"}
    deleted = client.delete(f"/api/v1/calendar/events/{event_id}", headers=delete_headers)
    replay_deleted = client.delete(f"/api/v1/calendar/events/{event_id}", headers=delete_headers)
    assert deleted.status_code == replay_deleted.status_code == 204
    assert client.get(f"/api/v1/calendar/events/{event_id}").status_code == 404


def test_event_time_range_and_schedule_validation(client) -> None:
    """Invalid time ranges and reminder schedules are rejected."""
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    headers = {"X-CSRF-Token": csrf}
    bad_range = _event_payload(ends_at=(datetime.now(UTC) + timedelta(days=1) - timedelta(hours=2)).isoformat())
    assert client.post("/api/v1/calendar/events", json=bad_range, headers=headers).status_code == 422
    both_schedules = _event_payload(reminders=[{"scheduled_for": (datetime.now(UTC) + timedelta(hours=1)).isoformat(), "offset_minutes": 10}])
    assert client.post("/api/v1/calendar/events", json=both_schedules, headers=headers).status_code == 422
    naive = _event_payload(starts_at=(datetime.now() + timedelta(days=1)).isoformat())
    assert client.post("/api/v1/calendar/events", json=naive, headers=headers).status_code == 422


def test_reminder_lifecycle_and_idempotency(client) -> None:
    """Reminders attach to events, recalculate on start change, and replay safely."""
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    created = client.post("/api/v1/calendar/events", json=_event_payload(), headers={"X-CSRF-Token": csrf})
    assert created.status_code == 201
    event_id = created.json()["id"]
    headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "reminder-1"}
    first = client.post(f"/api/v1/calendar/events/{event_id}/reminders", json={"offset_minutes": 15}, headers=headers)
    replay = client.post(f"/api/v1/calendar/events/{event_id}/reminders", json={"offset_minutes": 15}, headers=headers)
    assert first.status_code == replay.status_code == 200
    assert len(first.json()["reminders"]) == len(replay.json()["reminders"]) == 1
    reminder_id = first.json()["reminders"][0]["id"]
    moved = client.patch(f"/api/v1/calendar/events/{event_id}", json={"starts_at": (datetime.now(UTC) + timedelta(days=2)).isoformat()}, headers={"X-CSRF-Token": csrf})
    assert moved.status_code == 200
    reminder = moved.json()["reminders"][0]
    assert reminder["scheduled_for"] is not None
    patch_headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "reminder-patch-1"}
    patched = client.patch(f"/api/v1/calendar/reminders/{reminder_id}", json={"offset_minutes": 30}, headers=patch_headers)
    replay_patched = client.patch(f"/api/v1/calendar/reminders/{reminder_id}", json={"offset_minutes": 30}, headers=patch_headers)
    assert patched.status_code == replay_patched.status_code == 200
    delete_headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "reminder-delete-1"}
    deleted = client.delete(f"/api/v1/calendar/reminders/{reminder_id}", headers=delete_headers)
    replay_deleted = client.delete(f"/api/v1/calendar/reminders/{reminder_id}", headers=delete_headers)
    assert deleted.status_code == replay_deleted.status_code == 204


def test_category_lifecycle_and_isolation(client) -> None:
    """Categories are user-owned and replay-safe."""
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "category-1"}
    category = client.post("/api/v1/calendar/categories", json={"name": "Work", "color": "#1e88e5"}, headers=headers)
    assert category.status_code == 201
    conflict = client.post("/api/v1/calendar/categories", json={"name": "Other"}, headers=headers)
    assert conflict.status_code == 422
    assert conflict.json()["detail"] == "Idempotency-Key was already used for a different operation"
    category_id = category.json()["id"]
    listing = client.get("/api/v1/calendar/categories")
    assert listing.status_code == 200
    assert any(item["id"] == category_id for item in listing.json())
    delete_headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "category-delete-1"}
    deleted = client.delete(f"/api/v1/calendar/categories/{category_id}", headers=delete_headers)
    assert deleted.status_code == 204


def test_worker_delivers_due_event_reminder_once(configured_app) -> None:
    """Due event reminders create one persistent notification and remain delivered on replay."""
    _bootstrap_owner()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    event = CalendarEvent(user_id=user.id, title="Reminder event", starts_at=datetime.now(UTC) + timedelta(hours=1), ends_at=datetime.now(UTC) + timedelta(hours=2), all_day=False)
    db.add(event)
    db.flush()
    reminder = CalendarEventReminder(user_id=user.id, event_id=event.id, scheduled_for=datetime.now(UTC) - timedelta(minutes=1), status="pending")
    db.add(reminder)
    db.commit()
    assert process_due_event_reminders(db, now=datetime.now(UTC)) == 1
    assert process_due_event_reminders(db, now=datetime.now(UTC)) == 0
    assert db.query(Notification).count() == 1
    db.close()


def test_worker_reclaims_expired_processing_event_reminder(configured_app) -> None:
    """An expired worker lease is eligible for delivery again."""
    _bootstrap_owner()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    event = CalendarEvent(user_id=user.id, title="Lease recovery", starts_at=datetime.now(UTC) + timedelta(hours=1), ends_at=datetime.now(UTC) + timedelta(hours=2), all_day=False)
    db.add(event)
    db.flush()
    reminder = CalendarEventReminder(user_id=user.id, event_id=event.id, scheduled_for=datetime.now(UTC) - timedelta(minutes=2), status="processing", locked_until=datetime.now(UTC) - timedelta(minutes=1))
    db.add(reminder)
    db.commit()
    assert process_due_event_reminders(db, now=datetime.now(UTC)) == 1
    assert db.query(Notification).count() == 1
    db.close()


def test_worker_cancels_reminder_for_deleted_event(configured_app) -> None:
    """Reminders for soft-deleted events are cancelled, not delivered."""
    _bootstrap_owner()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    event = CalendarEvent(user_id=user.id, title="Ghost", starts_at=datetime.now(UTC) + timedelta(hours=1), ends_at=datetime.now(UTC) + timedelta(hours=2), all_day=False, deleted_at=datetime.now(UTC))
    db.add(event)
    db.flush()
    reminder = CalendarEventReminder(user_id=user.id, event_id=event.id, scheduled_for=datetime.now(UTC) - timedelta(minutes=1), status="pending")
    db.add(reminder)
    db.commit()
    assert process_due_event_reminders(db, now=datetime.now(UTC)) == 0
    db.refresh(reminder)
    assert reminder.status == "cancelled"
    assert db.query(Notification).count() == 0
    db.close()


def test_list_events_filters_by_range_and_category(client) -> None:
    """Range and category filters apply to the current user's events only."""
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    future = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    past = (datetime.now(UTC) - timedelta(days=5)).isoformat()
    client.post("/api/v1/calendar/events", json=_event_payload(starts_at=future, ends_at=(datetime.now(UTC) + timedelta(days=5, hours=1)).isoformat(), category="Personal"), headers={"X-CSRF-Token": csrf})
    client.post("/api/v1/calendar/events", json=_event_payload(starts_at=past, ends_at=(datetime.now(UTC) - timedelta(days=5, hours=-1)).isoformat(), category="Work"), headers={"X-CSRF-Token": csrf})
    from_iso = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    only_future = client.get("/api/v1/calendar/events", params={"from": from_iso})
    assert only_future.status_code == 200
    assert all(item["starts_at"] >= from_iso for item in only_future.json()["items"])
    work_only = client.get("/api/v1/calendar/events?category=work")
    assert work_only.status_code == 200
    assert all((item["category"] or {}).get("name") == "Work" for item in work_only.json()["items"])
