"""External source ingestion, lifecycle, and ownership tests."""

from pathlib import Path
from sqlalchemy import select

from app.db.models import Source, SourceChunk, User
from app.db.session import get_session_factory
from app.modules.identity.service import bootstrap_owner
from app.modules.sources.service import process_source_ingestion


def _login(client):
    db = get_session_factory()()
    try: bootstrap_owner(db, "owner", "correct horse battery staple")
    finally: db.close()
    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200
    return client.cookies.get("nexus_csrf")


def test_upload_is_queued_then_ingested_and_searchable(client):
    csrf = _login(client)
    response = client.post("/api/v1/sources/upload", headers={"X-CSRF-Token": csrf, "X-Source-Filename": "pi-plan.md", "Idempotency-Key": "source-1"}, content=b"Raspberry Pi deployment uses an external SSD.")
    assert response.status_code == 201, response.text
    source = response.json()
    assert source["status"] == "processing"
    db = get_session_factory()()
    try:
        settings = __import__("app.core.config", fromlist=["get_settings"]).get_settings()
        assert process_source_ingestion(db, settings) == 1
    finally: db.close()
    ready = client.get(f"/api/v1/sources/{source['id']}")
    assert ready.status_code == 200 and ready.json()["status"] == "ready"
    chunks = client.get(f"/api/v1/sources/{source['id']}/chunks")
    assert chunks.status_code == 200 and chunks.json()["items"]
    results = client.get("/api/v1/search/retrieve", params={"q": "external SSD", "mode": "lexical"})
    assert results.status_code == 200
    assert results.json()[0]["source_type"] == "external_source"


def test_upload_rejects_unsafe_or_binary_files(client):
    csrf = _login(client)
    unsafe = client.post("/api/v1/sources/upload", headers={"X-CSRF-Token": csrf, "X-Source-Filename": ".env", "Idempotency-Key": "source-bad-1"}, content=b"secret")
    assert unsafe.status_code == 422
    binary = client.post("/api/v1/sources/upload", headers={"X-CSRF-Token": csrf, "X-Source-Filename": "binary.txt", "Idempotency-Key": "source-bad-2"}, content=b"\xff\xfe")
    assert binary.status_code == 422


def test_source_lifecycle_is_owned_and_soft_deleted(client):
    csrf = _login(client)
    created = client.post("/api/v1/sources/upload", headers={"X-CSRF-Token": csrf, "X-Source-Filename": "private.txt", "Idempotency-Key": "source-life"}, content=b"private source")
    source_id = created.json()["id"]
    archived = client.post(f"/api/v1/sources/{source_id}/archive", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "source-archive"})
    assert archived.status_code == 200 and archived.json()["status"] == "archived"
    restored = client.post(f"/api/v1/sources/{source_id}/restore", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "source-restore"})
    assert restored.status_code == 200
    assert client.delete(f"/api/v1/sources/{source_id}", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "source-delete"}).status_code == 204
    assert client.get(f"/api/v1/sources/{source_id}").status_code == 404
