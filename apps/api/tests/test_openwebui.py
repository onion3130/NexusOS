"""Open WebUI Chat integration tests."""

from __future__ import annotations

from app.core.config import get_settings
from app.modules.identity.service import bootstrap_owner
from app.modules.system.openwebui import openwebui_status, validate_openwebui_url, write_openwebui_config
from app.modules.system.schemas import OpenWebUIConfigRequest
from app.db.session import get_session_factory


def _bootstrap_owner(username: str = "owner") -> None:
    db = get_session_factory()()
    try:
        bootstrap_owner(db, username, "correct horse battery staple")
    finally:
        db.close()


def _login(client, username: str = "owner") -> None:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "correct horse battery staple"})
    assert response.status_code == 200


def test_validate_openwebui_url_accepts_local_http() -> None:
    assert validate_openwebui_url("http://192.168.1.46:8080/") == "http://192.168.1.46:8080"
    assert validate_openwebui_url("https://chat.example.local") == "https://chat.example.local"


def test_validate_openwebui_url_rejects_credentials_and_junk() -> None:
    for bad in ("", "ftp://x", "http://user:pass@host/", "not-a-url", "http://host#frag"):
        try:
            validate_openwebui_url(bad)
            raise AssertionError(f"expected rejection for {bad!r}")
        except ValueError:
            pass


def test_openwebui_status_defaults_disabled(client) -> None:
    _bootstrap_owner()
    _login(client)
    response = client.get("/api/v1/system/openwebui")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["configured"] is False
    assert body["source"] == "none"


def test_openwebui_configure_and_read(client) -> None:
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    headers = {"X-CSRF-Token": csrf}
    created = client.post(
        "/api/v1/system/admin/openwebui",
        json={"enabled": True, "url": "http://192.168.1.46:8080", "label": "Studio", "embed": True},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["enabled"] is True
    assert body["url"] == "http://192.168.1.46:8080"
    assert body["label"] == "Studio"
    assert body["source"] == "browser"

    status = client.get("/api/v1/system/openwebui")
    assert status.status_code == 200
    assert status.json()["url"] == "http://192.168.1.46:8080"

    deleted = client.delete("/api/v1/system/admin/openwebui", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["source"] == "none"


def test_openwebui_env_fallback(client, monkeypatch, tmp_path) -> None:
    """OPENWEBUI_URL is used when no browser config exists."""
    from app.modules.system import openwebui as module

    settings = get_settings()
    # Ensure no browser file for this data dir.
    assert openwebui_status(settings).source in {"none", "environment"}

    monkeypatch.setenv("OPENWEBUI_URL", "http://10.0.0.5:8080")
    get_settings.cache_clear()
    refreshed = get_settings()
    status = openwebui_status(refreshed)
    assert status.enabled is True
    assert status.url == "http://10.0.0.5:8080"
    assert status.source == "environment"
    get_settings.cache_clear()


def test_write_openwebui_requires_url_when_enabled(client) -> None:
    settings = get_settings()
    try:
        write_openwebui_config(settings.data_dir, OpenWebUIConfigRequest(enabled=True, url=""))
        raise AssertionError("expected url required")
    except ValueError as exc:
        assert str(exc) == "openwebui_url_required"
