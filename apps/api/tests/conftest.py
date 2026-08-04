"""Shared test fixtures for the NexusOS API."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.rate_limit import reset_login_limits
from app.db.session import get_session_factory, reset_database_caches

API_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def configured_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Configure, migrate, and return the application against a fresh SQLite file."""
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
        "BACKUP_REPLICATION_DESTINATION": "",
        "BACKUP_ENCRYPTION_KEY": "",
        "MEDIA_ROOTS": str(tmp_path / "photos"),
        "MEDIA_THUMBNAIL_MAX_DIMENSION": "96",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    reset_database_caches()
    reset_login_limits()

    alembic_config = Config(str(API_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(API_ROOT / "migrations"))
    command.upgrade(alembic_config, "head")
    reset_database_caches()

    from app.main import app

    yield app
    get_session_factory.cache_clear()
    reset_database_caches()
    reset_login_limits()
    get_settings.cache_clear()


@pytest.fixture
def client(configured_app):
    """Return a TestClient for an isolated migrated application."""
    with TestClient(configured_app) as test_client:
        yield test_client
