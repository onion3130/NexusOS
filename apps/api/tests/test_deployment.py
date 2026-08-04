"""Milestone 10 deployment status tests."""

from __future__ import annotations

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.modules.identity.service import bootstrap_owner


def test_deployment_status_is_authenticated_and_redacted(client) -> None:
    """Deployment status exposes only bounded operational flags."""
    assert client.get("/api/v1/system/deployment").status_code == 401
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()
    assert client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"}).status_code == 200
    response = client.get("/api/v1/system/deployment")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "replication_configured": False,
        "tls_expected": False,
        "migration_head": "0013_finance",
    }
    assert "BACKUP_ENCRYPTION_KEY" not in response.text
    assert str(get_settings().data_dir) not in response.text
