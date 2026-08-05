"""Software update handshake tests (browser request / host agent status)."""

from __future__ import annotations

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.modules.identity.service import bootstrap_owner
from app.modules.system.software_update import _request_path, _status_path, read_software_update_status


def _bootstrap_owner() -> None:
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()


def _login(client):
    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200
    return client.cookies.get("nexus_csrf")


def test_software_update_requires_admin_and_csrf(client) -> None:
    assert client.get("/api/v1/system/admin/update").status_code == 401
    _bootstrap_owner()
    login = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200
    missing = client.post("/api/v1/system/admin/update", json={"action": "apply", "confirm": True})
    assert missing.status_code == 403


def test_software_update_queues_apply_with_confirm(client) -> None:
    _bootstrap_owner()
    csrf = _login(client)
    denied = client.post(
        "/api/v1/system/admin/update",
        headers={"X-CSRF-Token": csrf},
        json={"action": "apply", "confirm": False},
    )
    assert denied.status_code == 422
    assert denied.json()["detail"] == "confirm_required"

    queued = client.post(
        "/api/v1/system/admin/update",
        headers={"X-CSRF-Token": csrf},
        json={"action": "apply", "confirm": True},
    )
    assert queued.status_code == 200, queued.text
    body = queued.json()
    assert body["state"] == "queued"
    assert body["action"] == "apply"
    assert body["request_id"]
    settings = get_settings()
    assert _request_path(settings.data_dir).is_file()
    assert _status_path(settings.data_dir).is_file()
    status = client.get("/api/v1/system/admin/update")
    assert status.status_code == 200
    assert status.json()["state"] in {"queued", "agent_missing"}


def test_software_update_check_and_busy_guard(client) -> None:
    _bootstrap_owner()
    csrf = _login(client)
    first = client.post(
        "/api/v1/system/admin/update",
        headers={"X-CSRF-Token": csrf},
        json={"action": "check", "confirm": False},
    )
    assert first.status_code == 200
    assert first.json()["action"] == "check"
    second = client.post(
        "/api/v1/system/admin/update",
        headers={"X-CSRF-Token": csrf},
        json={"action": "check", "confirm": False},
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "update_busy"
    snapshot = read_software_update_status(get_settings())
    assert snapshot.can_request is False
