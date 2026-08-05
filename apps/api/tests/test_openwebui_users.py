"""Open WebUI account provisioning tests."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.core.config import get_settings
from app.modules.identity.service import bootstrap_owner, create_user
from app.modules.system.openwebui_users import nexus_username_to_email, provision_openwebui_user
from app.db.session import get_session_factory


def _bootstrap_owner() -> None:
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()


def _login(client) -> None:
    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200


def test_nexus_username_to_email() -> None:
    assert nexus_username_to_email("Orion") == "orion@nexus.local"
    assert nexus_username_to_email("a_b-1") == "a_b-1@nexus.local"


def test_create_user_provisions_openwebui(client, monkeypatch) -> None:
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")

    calls: list[dict] = []

    async def fake_provision(settings, *, username, password, is_owner=False, display_name=None):
        from app.modules.system.openwebui_users import OpenWebUIProvisionResult

        calls.append({"username": username, "password": password, "is_owner": is_owner, "display_name": display_name})
        return OpenWebUIProvisionResult(ok=True, status="created", detail="openwebui_user_created", email=f"{username}@nexus.local", role="user")

    monkeypatch.setattr("app.api.routes.auth.provision_openwebui_user", fake_provision)

    response = client.post(
        "/api/v1/auth/users",
        json={"username": "alice", "password": "correct horse battery", "as_owner": False},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["username"] == "alice"
    assert body["openwebui_email"] == "alice@nexus.local"
    assert body["openwebui_status"] == "created"
    assert "member" in body["roles"] or "owner" not in body["roles"]
    assert calls and calls[0]["username"] == "alice"
    assert calls[0]["password"] == "correct horse battery"
    assert calls[0]["is_owner"] is False


def test_login_attempts_openwebui_provision(client, monkeypatch) -> None:
    _bootstrap_owner()
    calls: list[str] = []

    async def fake_provision(settings, *, username, password, is_owner=False, display_name=None):
        from app.modules.system.openwebui_users import OpenWebUIProvisionResult

        calls.append(username)
        return OpenWebUIProvisionResult(ok=True, status="exists", detail="openwebui_user_exists", email=f"{username}@nexus.local")

    monkeypatch.setattr("app.api.routes.auth.provision_openwebui_user", fake_provision)
    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200
    assert calls == ["owner"]


def test_list_users_requires_admin(client) -> None:
    _bootstrap_owner()
    assert client.get("/api/v1/auth/users").status_code == 401
    _login(client)
    response = client.get("/api/v1/auth/users")
    assert response.status_code == 200
    assert any(item["username"] == "owner" for item in response.json())
