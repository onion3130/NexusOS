"""URL source ingestion, SSRF, and worker tests (v1.7)."""

from __future__ import annotations

from app.db.models import Job, Source
from app.db.session import get_session_factory
from app.modules.identity.service import bootstrap_owner
from app.modules.sources.fetch import content_type_extension, process_source_fetching, validate_fetch_url
from app.modules.sources.service import process_source_ingestion


def _login(client):
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()
    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200
    return client.cookies.get("nexus_csrf")


def test_validate_fetch_url_rejects_internal_and_credential_targets() -> None:
    for bad in (
        "http://example.com/page",
        "https://127.0.0.1/private",
        "https://localhost/docs",
        "https://192.168.1.5/intranet",
        "https://10.0.0.1/x",
        "https://[::1]/x",
        "https://169.254.169.254/latest/meta-data",
        "https://metadata.google.internal/computeMetadata/v1/",
        "ftp://example.com/file",
        "file:///etc/passwd",
        "https://user:pass@example.com/page",
    ):
        try:
            validate_fetch_url(bad)
        except ValueError as exc:
            assert str(exc) in {"url_scheme_not_allowed", "url_credentials_not_allowed", "url_target_not_allowed"}, (bad, str(exc))
        else:
            raise AssertionError(f"expected rejection for {bad}")
    assert validate_fetch_url("https://example.com/docs/page.html") == "https://example.com/docs/page.html"


def test_content_type_extension_mapping() -> None:
    assert content_type_extension("text/html") == ".html"
    assert content_type_extension("application/pdf") == ".pdf"
    assert content_type_extension("text/markdown; charset=utf-8") == ".md"
    assert content_type_extension("application/zip") is None
    assert content_type_extension("image/png") is None


def test_url_source_endpoint_validates_scheme_and_target(client) -> None:
    csrf = _login(client)
    bad_scheme = client.post("/api/v1/sources/url", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "url-bad-1"}, json={"url": "ftp://example.com/file"})
    assert bad_scheme.status_code == 422
    assert bad_scheme.json()["detail"] == "url_scheme_not_allowed"
    plain_http = client.post("/api/v1/sources/url", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "url-bad-3"}, json={"url": "http://example.com/page"})
    assert plain_http.status_code == 422
    assert plain_http.json()["detail"] == "url_scheme_not_allowed"
    loopback = client.post("/api/v1/sources/url", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "url-bad-2"}, json={"url": "https://127.0.0.1/private"})
    assert loopback.status_code == 422
    assert loopback.json()["detail"] == "url_target_not_allowed"
    missing_csrf = client.post("/api/v1/sources/url", json={"url": "https://example.com/"})
    assert missing_csrf.status_code == 403


def test_url_source_fetch_and_ingestion_flow(client, monkeypatch) -> None:
    import asyncio

    import app.modules.sources.fetch as fetch_module

    csrf = _login(client)
    created = client.post(
        "/api/v1/sources/url",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "url-ok-1"},
        json={"url": "https://example.com/guide", "title": "Setup guide"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["kind"] == "url"
    assert body["status"] == "processing"
    assert body["source_url"] == "https://example.com/guide"

    async def fake_fetch(url: str) -> tuple[str, bytes, str]:
        assert url == "https://example.com/guide"
        return url, b"<html><head><title>Setup guide</title></head><body><p>Raspberry Pi networking</p></body></html>", "text/html"

    monkeypatch.setattr(fetch_module, "_fetch_public_url", fake_fetch)
    db = get_session_factory()()
    try:
        from app.core.config import get_settings

        settings = get_settings()
        assert process_source_fetching(db, settings, batch_size=2) == 1
        source = db.query(Source).filter(Source.kind == "url").one()
        assert source.status == "processing"
        assert source.stored_path.endswith(".html")
        assert source.sha256
        assert source.title == "Setup guide"
        assert process_source_ingestion(db, settings, batch_size=2) == 1
        db.refresh(source)
        assert source.status == "ready"
        assert source.current_version == 1
    finally:
        db.close()

    ready = client.get(f"/api/v1/sources/{body['id']}")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    results = client.get("/api/v1/search/retrieve", params={"q": "networking", "mode": "lexical"})
    assert results.status_code == 200
    assert any(item["source_type"] == "external_source" for item in results.json())


def test_url_fetch_failure_is_recorded_and_retried(client, monkeypatch) -> None:
    import app.modules.sources.fetch as fetch_module

    csrf = _login(client)
    created = client.post(
        "/api/v1/sources/url",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "url-fail-1"},
        json={"url": "https://example.com/unreachable"},
    )
    source_id = created.json()["id"]

    async def failing_fetch(url: str) -> tuple[str, bytes, str]:
        raise ValueError("url_fetch_failed")

    monkeypatch.setattr(fetch_module, "_fetch_public_url", failing_fetch)
    db = get_session_factory()()
    try:
        from app.core.config import get_settings

        settings = get_settings()
        assert process_source_fetching(db, settings, batch_size=2) == 1
        source = db.get(Source, source_id)
        assert source is not None
        assert source.status == "failed"
        assert source.last_error_code == "url_fetch_failed"
        job = db.scalars(
            __import__("sqlalchemy").select(Job).where(Job.job_type == "source_fetch", Job.payload_json == source_id)
        ).one()
        assert job.status == "queued" and job.attempts == 1
    finally:
        db.close()


def test_url_source_reindex_queues_fetch_not_ingest(client) -> None:
    csrf = _login(client)
    created = client.post(
        "/api/v1/sources/url",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "url-reindex-1"},
        json={"url": "https://example.com/again"},
    )
    source_id = created.json()["id"]
    reindexed = client.post(f"/api/v1/sources/{source_id}/reindex", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "url-reindex-2"})
    assert reindexed.status_code == 200
    db = get_session_factory()()
    try:
        from sqlalchemy import select

        jobs = db.scalars(select(Job).where(Job.payload_json == source_id)).all()
        assert any(job.job_type == "source_fetch" for job in jobs)
    finally:
        db.close()
