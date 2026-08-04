"""Milestone 13 backup retention and lifecycle tests."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import AuditEvent, BackupRecord, User
from app.db.session import get_session_factory, reset_database_caches
from app.modules.backup_replication.encryption import EncryptionError, encrypt_file, verify_file
from app.modules.host_actions.backups import create_backup
from app.modules.host_actions.lifecycle import LifecycleError, prune_backups, retention_policy, rotate_encryption_keys
from app.modules.host_actions.worker import process_host_actions
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


def _record(user_id: str, created_at: datetime, *, status: str = "verified") -> BackupRecord:
    return BackupRecord(id=str(uuid4()), user_id=user_id, relative_path=f"backups/{os.urandom(8).hex()}.db", size_bytes=1, sha256="0" * 64, status=status, integrity_result="ok", created_at=created_at)


def _owner_id(db) -> str:
    return db.scalar(select(User).where(User.username == "owner")).id


def test_retention_policy_keeps_newest_and_recent(configured_app) -> None:
    """Backups beyond the count and the day window are pruned; recent ones are kept."""
    now = datetime.now(UTC)
    records = [
        _record("u", now),
        _record("u", now - timedelta(days=2)),
        _record("u", now - timedelta(days=10)),
        _record("u", now - timedelta(days=20)),
    ]
    to_prune, retained = retention_policy(records, retention_count=2, retention_days=7, now=now)
    assert {item.created_at for item in to_prune} == {records[2].created_at, records[3].created_at}
    assert {item.created_at for item in retained} == {records[0].created_at, records[1].created_at}


def test_retention_policy_always_keeps_newest(configured_app) -> None:
    """The newest verified backup survives even when count and days would prune all."""
    now = datetime.now(UTC)
    records = [_record("u", now - timedelta(days=10)), _record("u", now - timedelta(days=20))]
    to_prune, retained = retention_policy(records, retention_count=1, retention_days=1, now=now)
    assert len(to_prune) == 1
    assert retained == [records[0]]


def test_retention_policy_sole_backup_never_pruned(configured_app) -> None:
    """A single verified backup is always retained."""
    now = datetime.now(UTC)
    records = [_record("u", now - timedelta(days=90))]
    to_prune, retained = retention_policy(records, retention_count=1, retention_days=1, now=now)
    assert to_prune == []
    assert retained == records


def test_retention_policy_ignores_non_verified(configured_app) -> None:
    """Failed or pending records never participate in retention decisions."""
    now = datetime.now(UTC)
    records = [
        _record("u", now - timedelta(days=60), status="failed"),
        _record("u", now - timedelta(days=60), status="created"),
        _record("u", now),
    ]
    to_prune, retained = retention_policy(records, retention_count=1, retention_days=1, now=now)
    assert to_prune == []
    assert retained == [records[2]]


def test_prune_deletes_local_and_encrypted_artifacts(configured_app) -> None:
    """Pruning removes both artifacts and soft-deletes the record with an audit row."""
    _bootstrap()
    settings = get_settings()
    key = os.urandom(32).hex()
    destination = settings.data_dir / "off-host"
    db = get_session_factory()()
    user_id = _owner_id(db)
    record = create_backup(settings.data_dir, settings.database_url, user_id, db)
    artifact = destination / "encrypted" / f"{record.id}.nxb"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    encrypt_file(settings.data_dir / record.relative_path, artifact, key)
    record.encryption_status = "encrypted"
    record.encrypted_relative_path = f"encrypted/{record.id}.nxb"
    record.replication_status = "replicated"
    db.commit()

    local = settings.data_dir / record.relative_path
    assert local.is_file() and artifact.is_file()
    summary = prune_backups(settings.data_dir, db, [record], user_id=user_id, replication_destination=destination)
    assert summary["pruned"] == 1 and summary["skipped"] == 0
    assert not local.exists() and not artifact.exists()
    assert record.status == "deleted" and record.pruned_at is not None
    assert record.replication_status == "deleted"
    audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "backup_retention.prune"))
    assert audit is not None and audit.result == "success"
    db.close()


def test_prune_skips_digest_mismatch(configured_app) -> None:
    """A tampered artifact is reported and never silently deleted."""
    _bootstrap()
    settings = get_settings()
    db = get_session_factory()()
    user_id = _owner_id(db)
    record = create_backup(settings.data_dir, settings.database_url, user_id, db)
    path = settings.data_dir / record.relative_path
    with path.open("ab") as stream:
        stream.write(b"tampered")
    summary = prune_backups(settings.data_dir, db, [record], user_id=user_id)
    assert summary["pruned"] == 0 and summary["skipped"] == 1
    assert path.exists()
    assert record.status == "verified" and record.pruned_at is None
    db.close()


def test_prune_rejects_path_escape(configured_app) -> None:
    """A record whose path escapes the data volume is never deleted."""
    _bootstrap()
    settings = get_settings()
    db = get_session_factory()()
    record = _record(_owner_id(db), datetime.now(UTC))
    record.relative_path = "../../escape.db"
    with pytest.raises(LifecycleError):
        prune_backups(settings.data_dir, db, [record], user_id=record.user_id)
    db.close()


def test_prune_encrypted_without_destination_fails_closed(configured_app) -> None:
    """An encrypted record with no configured destination fails closed before deleting."""
    _bootstrap()
    settings = get_settings()
    db = get_session_factory()()
    user_id = _owner_id(db)
    record = create_backup(settings.data_dir, settings.database_url, user_id, db)
    record.encryption_status = "encrypted"
    record.encrypted_relative_path = f"encrypted/{record.id}.nxb"
    db.commit()
    with pytest.raises(LifecycleError):
        prune_backups(settings.data_dir, db, [record], user_id=user_id)
    assert (settings.data_dir / record.relative_path).exists()
    assert record.status == "verified"
    db.close()


def test_rotation_requires_keys_and_rejects_identical(configured_app) -> None:
    """Rotation fails closed when keys are missing or identical."""
    _bootstrap()
    settings = get_settings()
    db = get_session_factory()()
    key_a = os.urandom(32).hex()
    with pytest.raises(LifecycleError):
        rotate_encryption_keys(db=db, user_id=_owner_id(db), destination=None, current_key=None, previous_key=key_a)
    with pytest.raises(LifecycleError):
        rotate_encryption_keys(db=db, user_id=_owner_id(db), destination=settings.data_dir / "x", current_key=key_a, previous_key=key_a)
    db.close()


def test_rotation_reencrypts_artifacts_and_is_idempotent(configured_app) -> None:
    """Rotation re-encrypts with the new key, is idempotent, and updates metadata."""
    _bootstrap()
    settings = get_settings()
    key_a = os.urandom(32).hex()
    key_b = os.urandom(32).hex()
    destination = settings.data_dir / "off-host"
    db = get_session_factory()()
    user_id = _owner_id(db)
    record = create_backup(settings.data_dir, settings.database_url, user_id, db)
    artifact = destination / "encrypted" / f"{record.id}.nxb"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    encrypt_file(settings.data_dir / record.relative_path, artifact, key_a)
    record.encryption_status = "encrypted"
    record.encrypted_relative_path = f"encrypted/{record.id}.nxb"
    record.replication_status = "replicated"
    db.commit()

    assert rotate_encryption_keys(db=db, user_id=user_id, destination=destination, current_key=key_b, previous_key=key_a) == {"rotated": 1}
    _size, digest = verify_file(artifact, key_b)
    assert digest == record.encrypted_sha256
    with pytest.raises(EncryptionError):
        verify_file(artifact, key_a)
    # A retry is a no-op: the artifact already verifies under the current key.
    assert rotate_encryption_keys(db=db, user_id=user_id, destination=destination, current_key=key_b, previous_key=key_a) == {"rotated": 0}
    db.close()


def test_retention_preview_endpoint_shape_and_policy(client) -> None:
    """The preview is authenticated, echoes the policy, and lists prunable items."""
    _bootstrap()
    assert client.get("/api/v1/system/backups/retention-preview").status_code == 401
    _login(client)
    settings = get_settings()
    db = get_session_factory()()
    user_id = _owner_id(db)
    create_backup(settings.data_dir, settings.database_url, user_id, db)  # recent, always retained
    for _ in range(7):
        record = create_backup(settings.data_dir, settings.database_url, user_id, db)
        record.created_at = datetime.now(UTC) - timedelta(days=40)
    db.commit()
    db.close()

    response = client.get("/api/v1/system/backups/retention-preview")
    assert response.status_code == 200
    body = response.json()
    assert body["policy"] == {"count": 7, "days": 30}
    assert len(body["to_prune"]) == 1
    assert len(body["retained"]) == 7


def test_retention_cleanup_via_proposal_pipeline(client) -> None:
    """A confirmed retention proposal prunes through the worker and is audited."""
    _bootstrap()
    _login(client)
    csrf = _csrf(client)
    settings = get_settings()
    db = get_session_factory()()
    user_id = _owner_id(db)
    older = create_backup(settings.data_dir, settings.database_url, user_id, db)
    newer = create_backup(settings.data_dir, settings.database_url, user_id, db)
    older.created_at = datetime.now(UTC) - timedelta(days=40)
    db.commit()

    created = client.post(
        "/api/v1/system/actions/proposals",
        json={"action_key": "maintenance.retention_cleanup", "input": {}},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "retention-propose"},
    )
    assert created.status_code == 201
    assert created.json()["risk_level"] == "medium"
    queued = client.post(
        f"/api/v1/system/actions/proposals/{created.json()['id']}/confirm",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "retention-confirm"},
    )
    assert queued.status_code == 200 and queued.json()["status"] == "queued"

    assert process_host_actions(db, data_dir=settings.data_dir, database_url=settings.database_url, retention_count=1, retention_days=1) == 1
    pruned = db.get(BackupRecord, older.id)
    assert pruned is not None and pruned.status == "deleted" and pruned.pruned_at is not None
    assert db.get(BackupRecord, newer.id).status == "verified"
    db.close()

    reset_database_caches()
    remaining = client.get("/api/v1/system/backups").json()
    assert [item["id"] for item in remaining] == [newer.id]
    audit = client.get("/api/v1/system/audit").json()["items"]
    assert any(item["action"] == "host_action.execute" and item["result"] == "success" for item in audit)


def test_rotation_via_proposal_pipeline(client) -> None:
    """A confirmed rotation proposal re-encrypts artifacts through the worker."""
    _bootstrap()
    _login(client)
    csrf = _csrf(client)
    settings = get_settings()
    key_a = os.urandom(32).hex()
    key_b = os.urandom(32).hex()
    destination = settings.data_dir / "off-host"
    db = get_session_factory()()
    user_id = _owner_id(db)
    record = create_backup(settings.data_dir, settings.database_url, user_id, db)
    artifact = destination / "encrypted" / f"{record.id}.nxb"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    encrypt_file(settings.data_dir / record.relative_path, artifact, key_a)
    record.encryption_status = "encrypted"
    record.encrypted_relative_path = f"encrypted/{record.id}.nxb"
    record.replication_status = "replicated"
    db.commit()

    created = client.post(
        "/api/v1/system/actions/proposals",
        json={"action_key": "maintenance.rotate_encryption_key", "input": {}},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "rotate-propose"},
    )
    assert created.status_code == 201
    assert created.json()["risk_level"] == "high"
    queued = client.post(
        f"/api/v1/system/actions/proposals/{created.json()['id']}/confirm",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "rotate-confirm"},
    )
    assert queued.status_code == 200 and queued.json()["status"] == "queued"

    assert process_host_actions(db, data_dir=settings.data_dir, database_url=settings.database_url, replication_destination=destination, encryption_key=key_b, previous_encryption_key=key_a) == 1
    db.close()

    _size, digest = verify_file(artifact, key_b)
    assert digest == record.encrypted_sha256
    with pytest.raises(EncryptionError):
        verify_file(artifact, key_a)
    assert any(item["action"] == "host_action.execute" and item["result"] == "success" for item in client.get("/api/v1/system/audit").json()["items"])
