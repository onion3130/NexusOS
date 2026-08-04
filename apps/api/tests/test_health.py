"""Tests for the NexusOS health contract."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import reset_database_caches


def _configure(monkeypatch, tmp_path) -> None:
    values = {
        "NEXUS_ENV": "test",
        "TZ": "UTC",
        "DATA_DIR": str(tmp_path),
        "DB_TYPE": "sqlite",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'nexus.db'}",
        "JWT_SECRET": "test-secret-that-is-longer-than-thirty-two-characters",
        "SESSION_COOKIE_SECURE": "false",
        "CORS_ORIGINS": "http://localhost:3000",
        "AI_PROVIDER": "disabled",
        "EMBEDDING_PROVIDER": "disabled",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    reset_database_caches()


def test_live_endpoint_does_not_require_storage(monkeypatch, tmp_path) -> None:
    """Liveness remains available even when the storage path is absent."""
    _configure(monkeypatch, tmp_path / "missing")
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "nexus-api",
        "version": "1.3.2",
    }


def test_ready_endpoint_reports_unmigrated_database(monkeypatch, tmp_path) -> None:
    """Readiness reports storage and refuses an un-migrated database."""
    _configure(monkeypatch, tmp_path)
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["storage"]["status"] == "ok"
    assert response.json()["checks"]["database"]["reason"] == "migration_required"


def test_startup_rejects_placeholder_secret(monkeypatch, tmp_path) -> None:
    """Startup errors identify the setting without exposing its value."""
    _configure(monkeypatch, tmp_path)
    monkeypatch.setenv("JWT_SECRET", "generate_a_random_secret_here")
    get_settings.cache_clear()
    from app.main import app

    try:
        with TestClient(app):
            raise AssertionError("application unexpectedly started")
    except RuntimeError as exc:
        assert "JWT_SECRET" in str(exc)
        assert "generate_a_random_secret_here" not in str(exc)
