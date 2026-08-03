"""Milestone 2 identity and session API tests."""

from __future__ import annotations

from app.core.security import hash_password, verify_password
from app.db.session import get_session_factory
from app.modules.identity.service import bootstrap_owner


def _bootstrap_owner() -> None:
    """Create the fixture owner through the same service as the CLI."""
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()


def test_password_hashing_is_not_reversible() -> None:
    """Argon2 verifies the password without storing it directly."""
    password = "correct horse battery staple"
    password_hash = hash_password(password)
    assert password_hash != password
    assert verify_password(password_hash, password)
    assert not verify_password(password_hash, "wrong password")


def test_login_me_sessions_and_csrf_logout(client) -> None:
    """Login establishes cookies; cookie mutations require CSRF."""
    _bootstrap_owner()

    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200
    assert {"nexus_access", "nexus_refresh", "nexus_csrf"}.issubset(response.cookies.keys())

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "owner"
    assert me.json()["roles"] == ["owner"]

    sessions = client.get("/api/v1/auth/sessions")
    assert sessions.status_code == 200
    assert len(sessions.json()) == 1

    blocked_logout = client.post("/api/v1/auth/logout")
    assert blocked_logout.status_code == 403

    csrf = client.cookies.get("nexus_csrf")
    logout = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_invalid_login_is_generic_and_refresh_rotates(client) -> None:
    """Invalid credentials do not authenticate; refresh requires and rotates CSRF."""
    _bootstrap_owner()

    invalid = client.post("/api/v1/auth/login", json={"username": "missing-user", "password": "wrong password"})
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "Invalid username or password"

    login = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200
    old_refresh = client.cookies.get("nexus_refresh")
    old_csrf = client.cookies.get("nexus_csrf")

    blocked = client.post("/api/v1/auth/refresh")
    assert blocked.status_code == 403

    refreshed = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": old_csrf})
    assert refreshed.status_code == 200
    assert client.cookies.get("nexus_refresh") != old_refresh
    assert client.cookies.get("nexus_csrf") != old_csrf

    client.cookies.set("nexus_refresh", old_refresh)
    client.cookies.set("nexus_csrf", old_csrf)
    replay = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": old_csrf})
    assert replay.status_code in {401, 403}
