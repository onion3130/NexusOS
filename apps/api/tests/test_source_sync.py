"""Approved-root source synchronization tests."""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.modules.sources.service import process_source_ingestion
from app.modules.sources.sync import process_source_sync


def _login(client):
    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200
    return client.cookies.get("nexus_csrf")


def test_approved_file_sync_detects_changes_and_creates_new_version(client):
    db = get_session_factory()()
    try:
        from app.modules.identity.service import bootstrap_owner
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()
    csrf = _login(client)
    settings = get_settings()
    path = Path(settings.data_dir) / "knowledge.md"
    path.write_text("first version", encoding="utf-8")
    discovered = client.get("/api/v1/sources/approved-files")
    assert discovered.status_code == 200
    file = next(item for item in discovered.json()["items"] if item["name"] == "knowledge.md")
    created = client.post("/api/v1/sources/import-approved-file", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "sync-import"}, json={"file_id": file["file_id"]})
    assert created.status_code == 201, created.text
    source = created.json()
    source_id = source["id"]
    db = get_session_factory()()
    try:
        assert process_source_ingestion(db, settings) == 1
    finally:
        db.close()
    enabled = client.post(f"/api/v1/sources/{source_id}/sync", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "sync-enable"}, json={"enabled": True, "interval_seconds": 900})
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["enabled"] is True
    path.write_text("second version", encoding="utf-8")
    db = get_session_factory()()
    try:
        assert process_source_sync(db, settings, batch_size=2) >= 1
        assert process_source_ingestion(db, settings, batch_size=2) == 1
    finally:
        db.close()
    current = client.get(f"/api/v1/sources/{source_id}")
    assert current.status_code == 200
    assert current.json()["status"] == "ready"
    assert current.json()["current_version"] == 2
    assert current.json()["sync"]["last_changed_at"] is not None


def test_source_sync_requires_approved_file_and_csrf(client):
    db = get_session_factory()()
    try:
        from app.modules.identity.service import bootstrap_owner
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()
    csrf = _login(client)
    uploaded = client.post("/api/v1/sources/upload", headers={"X-CSRF-Token": csrf, "X-Source-Filename": "manual.txt", "Idempotency-Key": "manual-source"}, content=b"manual")
    assert uploaded.status_code == 201
    source_id = uploaded.json()["id"]
    missing_csrf = client.post(f"/api/v1/sources/{source_id}/sync", json={"enabled": True, "interval_seconds": 900})
    assert missing_csrf.status_code == 403
    not_supported = client.post(f"/api/v1/sources/{source_id}/sync", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "manual-sync"}, json={"enabled": True, "interval_seconds": 900})
    assert not_supported.status_code == 422


def test_source_sync_no_change_is_successful_and_disable_stops_schedule(client):
    db = get_session_factory()()
    try:
        from app.modules.identity.service import bootstrap_owner
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()
    csrf = _login(client)
    settings = get_settings()
    path = Path(settings.data_dir) / "stable.txt"
    path.write_text("stable", encoding="utf-8")
    file = next(item for item in client.get("/api/v1/sources/approved-files").json()["items"] if item["name"] == "stable.txt")
    created = client.post("/api/v1/sources/import-approved-file", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "stable-import"}, json={"file_id": file["file_id"]})
    source_id = created.json()["id"]
    db = get_session_factory()()
    try:
        process_source_ingestion(db, settings)
    finally:
        db.close()
    client.post(f"/api/v1/sources/{source_id}/sync", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "stable-enable"}, json={"enabled": True, "interval_seconds": 900})
    db = get_session_factory()()
    try:
        assert process_source_sync(db, settings) >= 1
    finally:
        db.close()
    status = client.get(f"/api/v1/sources/{source_id}/sync")
    assert status.status_code == 200 and status.json()["last_success_at"] is not None
    disabled = client.delete(f"/api/v1/sources/{source_id}/sync", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "stable-disable"})
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False and disabled.json()["next_check_at"] is None
