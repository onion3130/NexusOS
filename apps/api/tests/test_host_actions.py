"""Milestone 8 safe host-action and backup tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import AuditEvent, BackupRecord, HostActionProposal, Job, User
from app.db.session import get_session_factory
from app.modules.host_actions.backups import BackupError, database_path, verify_backup
from app.modules.host_actions.worker import MAX_ATTEMPTS, process_host_actions
from app.modules.identity.service import bootstrap_owner


def _bootstrap() -> None:
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()


def _login(client) -> None:
    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200


def _csrf(client) -> str:
    token = client.cookies.get("nexus_csrf")
    assert token
    return token


def test_catalog_is_allowlisted_and_proposal_does_not_execute(client) -> None:
    """The catalog exposes only fixed actions and proposal creation is inert."""
    _bootstrap()
    _login(client)
    catalog = client.get("/api/v1/system/actions")
    assert catalog.status_code == 200
    assert {item["key"] for item in catalog.json()} == {
        "maintenance.create_backup",
        "maintenance.verify_backup",
        "maintenance.integrity_check",
        "maintenance.restore_backup",
    }
    restore = client.post(
        "/api/v1/system/actions/proposals",
        json={"action_key": "maintenance.restore_backup", "input": {"backup_id": "not-a-real-id"}},
        headers={"X-CSRF-Token": _csrf(client), "Idempotency-Key": "restore-input"},
    )
    assert restore.status_code == 201
    assert restore.json()["risk_level"] == "high"
    unsafe = client.post(
        "/api/v1/system/actions/proposals",
        json={"action_key": "maintenance.restore_backup", "input": {"path": "/etc", "backup_id": "x"}},
        headers={"X-CSRF-Token": _csrf(client), "Idempotency-Key": "restore-unsafe"},
    )
    assert unsafe.status_code == 422
    response = client.post(
        "/api/v1/system/actions/proposals",
        json={"action_key": "maintenance.create_backup", "input": {"command": "rm -rf /"}},
        headers={"X-CSRF-Token": _csrf(client), "Idempotency-Key": "unsafe-input"},
    )
    assert response.status_code == 422
    assert client.get("/api/v1/system/backups").json() == []
    response = client.post(
        "/api/v1/system/actions/proposals",
        json={"action_key": "maintenance.create_backup", "input": {}},
        headers={"X-CSRF-Token": _csrf(client), "Idempotency-Key": "backup-request"},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "proposed"
    assert response.json()["job_id"] is None
    assert client.get("/api/v1/system/backups").json() == []


def test_confirmation_queues_job_and_worker_creates_verified_backup(client) -> None:
    """Only explicit confirmation queues work; the worker creates an audited verified backup."""
    _bootstrap()
    _login(client)
    csrf = _csrf(client)
    proposal = client.post(
        "/api/v1/system/actions/proposals",
        json={"action_key": "maintenance.create_backup", "input": {}},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "backup-request"},
    ).json()
    confirmed = client.post(
        f"/api/v1/system/actions/proposals/{proposal['id']}/confirm",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "backup-confirm"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "queued"
    assert confirmed.json()["job_id"]
    assert client.get("/api/v1/system/backups").json() == []
    settings = get_settings()
    db = get_session_factory()()
    try:
        assert process_host_actions(db, data_dir=settings.data_dir, database_url=settings.database_url) == 1
    finally:
        db.close()
    completed = client.get(f"/api/v1/system/actions/proposals/{proposal['id']}").json()
    assert completed["status"] == "succeeded"
    backups = client.get("/api/v1/system/backups")
    assert backups.status_code == 200
    assert len(backups.json()) == 1
    assert backups.json()[0]["status"] == "verified"
    assert backups.json()[0]["integrity_result"] == "ok"
    audit = client.get("/api/v1/system/audit")
    assert audit.status_code == 200
    assert {item["action"] for item in audit.json()["items"]} >= {"host_action.propose", "host_action.confirm", "host_action.execute"}


def test_reject_never_creates_job_and_requires_csrf(client) -> None:
    """Rejecting is audited and cannot be performed by a cookie client without CSRF."""
    _bootstrap()
    _login(client)
    proposal = client.post(
        "/api/v1/system/actions/proposals",
        json={"action_key": "maintenance.integrity_check", "input": {}},
        headers={"X-CSRF-Token": _csrf(client), "Idempotency-Key": "integrity-request"},
    ).json()
    blocked = client.post(f"/api/v1/system/actions/proposals/{proposal['id']}/reject")
    assert blocked.status_code == 403
    rejected = client.post(f"/api/v1/system/actions/proposals/{proposal['id']}/reject", headers={"X-CSRF-Token": _csrf(client)})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    db = get_session_factory()()
    try:
        assert db.query(Job).filter(Job.job_type == "host_action").count() == 0
        item = db.get(HostActionProposal, proposal["id"])
        assert item is not None and item.status == "rejected"
    finally:
        db.close()


def test_proposal_expiry_is_enforced(client) -> None:
    """An expired proposal transitions to expired and cannot enqueue work."""
    _bootstrap()
    _login(client)
    proposal = client.post(
        "/api/v1/system/actions/proposals",
        json={"action_key": "maintenance.integrity_check", "input": {}},
        headers={"X-CSRF-Token": _csrf(client), "Idempotency-Key": "expired-request"},
    ).json()
    db = get_session_factory()()
    try:
        item = db.get(HostActionProposal, proposal["id"])
        assert item is not None
        item.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    response = client.post(f"/api/v1/system/actions/proposals/{proposal['id']}/confirm", headers={"X-CSRF-Token": _csrf(client)})
    assert response.status_code == 200
    assert response.json()["status"] == "expired"


def test_jobs_and_audit_are_user_scoped_and_unauthenticated_is_blocked(client) -> None:
    """Operational records never become public endpoints."""
    assert client.get("/api/v1/system/actions").status_code == 401
    assert client.get("/api/v1/system/backups").status_code == 401
    assert client.get("/api/v1/system/audit").status_code == 401


def test_backup_paths_are_confined_to_data_dir(tmp_path: Path) -> None:
    """Database source paths cannot escape the configured data volume or backups child."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    database = data_dir / "nexus.db"
    database.touch()
    assert database_path(f"sqlite:///{database}", data_dir) == database.resolve()
    with pytest.raises(BackupError):
        database_path(f"sqlite:///{tmp_path / 'outside.db'}", data_dir)
    backup = data_dir / "backups" / "nested.db"
    backup.parent.mkdir()
    backup.touch()
    with pytest.raises(BackupError):
        database_path(f"sqlite:///{backup}", data_dir)


def test_tampered_backup_is_not_marked_verified(configured_app, tmp_path: Path) -> None:
    """Digest mismatch fails verification and retains the original trusted digest."""
    _bootstrap()
    settings = get_settings()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    record = BackupRecord(
        user_id=user.id,
        relative_path="backups/tampered.db",
        size_bytes=4,
        sha256="0" * 64,
        status="verified",
        integrity_result="ok",
    )
    path = settings.data_dir / record.relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not-a-sqlite-backup")
    db.add(record)
    db.commit()
    original_digest = record.sha256
    try:
        checked = verify_backup(settings.data_dir, record)
        assert checked.status == "failed"
        assert checked.sha256 == original_digest
    finally:
        db.close()


def test_verified_backup_retry_rebuilds_missing_artifact(configured_app) -> None:
    """A missing artifact cannot be reported as verified and is rebuilt on retry."""
    _bootstrap()
    settings = get_settings()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    operation_id = "nexus-retry"
    path = settings.data_dir / "backups" / f"nexus-{operation_id}.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"partial")
    record = BackupRecord(
        user_id=user.id,
        relative_path=str(path.relative_to(settings.data_dir)),
        size_bytes=7,
        sha256="0" * 64,
        status="verified",
        integrity_result="ok",
    )
    db.add(record)
    db.commit()
    try:
        from app.modules.host_actions.backups import create_backup
        rebuilt = create_backup(settings.data_dir, settings.database_url, user.id, db, operation_id=operation_id)
        assert rebuilt.status == "verified"
        assert rebuilt.sha256 != "0" * 64
        assert db.query(BackupRecord).count() == 1
    finally:
        db.close()


def test_worker_retries_stale_jobs_and_uses_one_backup_per_job(client) -> None:
    """A crashed processing lease is reclaimed and retrying a backup does not duplicate files."""
    _bootstrap()
    _login(client)
    csrf = _csrf(client)
    proposal = client.post(
        "/api/v1/system/actions/proposals",
        json={"action_key": "maintenance.create_backup", "input": {}},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "retry-request"},
    ).json()
    confirmed = client.post(
        f"/api/v1/system/actions/proposals/{proposal['id']}/confirm",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "retry-confirm"},
    ).json()
    db = get_session_factory()()
    settings = get_settings()
    try:
        job = db.get(Job, confirmed["job_id"])
        assert job is not None
        job.status = "processing"
        job.attempts = 1
        job.locked_until = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
        assert process_host_actions(db, data_dir=settings.data_dir, database_url=settings.database_url) == 1
        assert db.get(HostActionProposal, proposal["id"]).status == "succeeded"
        assert db.query(BackupRecord).count() == 1
    finally:
        db.close()


def test_worker_exhausts_retries_and_audits_failure(configured_app) -> None:
    """Malformed durable jobs become terminal after the bounded retry limit."""
    _bootstrap()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    proposal = HostActionProposal(
        user_id=user.id,
        action_key="maintenance.integrity_check",
        risk_level="medium",
        status="processing",
        input_json="{}",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    db.add(proposal)
    db.flush()
    job = Job(
        job_type="host_action",
        status="processing",
        payload_json="{\"proposal_id\":\"" + proposal.id + "\"}",
        available_at=datetime.now(UTC),
        attempts=MAX_ATTEMPTS,
        locked_until=datetime.now(UTC) - timedelta(minutes=1),
    )
    db.add(job)
    db.commit()
    try:
        assert process_host_actions(db, data_dir=get_settings().data_dir, database_url=get_settings().database_url) == 0
        db.refresh(proposal)
        db.refresh(job)
        assert proposal.status == "failed"
        assert job.status == "failed"
        assert db.scalar(select(AuditEvent).where(AuditEvent.target == proposal.id, AuditEvent.result == "failure")) is not None
    finally:
        db.close()
