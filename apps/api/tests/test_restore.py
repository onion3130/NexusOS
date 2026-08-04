"""Milestone 12 confirmation-gated restore tests."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import BackupRecord, Task as TaskModel, User
from app.db.session import get_session_factory, reset_database_caches
from app.modules.backup_replication.encryption import EncryptionError, decrypt_file, encrypt_file
from app.modules.host_actions.backups import create_backup
from app.modules.host_actions.restore import RestoreError, restore_backup
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


def _add_task(db, user_id: str, title: str) -> None:
    db.add(TaskModel(user_id=user_id, title=title, status="open", priority="normal"))
    db.commit()


def _live_titles() -> set[str]:
    db = get_session_factory()()
    try:
        return {item.title for item in db.scalars(select(TaskModel).where(TaskModel.title.in_(["marker-a", "marker-b"])))}
    finally:
        db.close()


def test_decrypt_file_roundtrip_and_tamper(tmp_path) -> None:
    """Decryption is the authenticated mirror of encryption and detects tampering."""
    key = os.urandom(32).hex()
    source = tmp_path / "source.bin"
    payload = os.urandom(3 * 1024 * 1024 + 123)
    source.write_bytes(payload)
    encrypted = tmp_path / "source.nxb"
    plain = tmp_path / "restored.bin"
    encrypt_file(source, encrypted, key)
    total, digest = decrypt_file(encrypted, plain, key)
    assert total == len(payload)
    assert plain.read_bytes() == payload
    assert digest == hashlib.sha256(payload).hexdigest()

    tampered = bytearray(encrypted.read_bytes())
    tampered[len(tampered) // 2] ^= 0xFF
    encrypted.write_bytes(bytes(tampered))
    with pytest.raises(EncryptionError):
        decrypt_file(encrypted, plain, key)

    encrypted.write_bytes(encrypted.read_bytes()[:-10])
    with pytest.raises(EncryptionError):
        decrypt_file(encrypted, plain, key)


def test_restore_from_local_verified_backup(configured_app) -> None:
    """A verified local backup replaces the live database with a safety backup."""
    _bootstrap()
    settings = get_settings()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    _add_task(db, user.id, "marker-a")
    record = create_backup(settings.data_dir, settings.database_url, user.id, db)
    assert record.status == "verified"
    _add_task(db, user.id, "marker-b")
    record = db.get(BackupRecord, record.id)
    result = restore_backup(settings.data_dir, settings.database_url, record, db)
    assert result["restart_required"] is True
    assert result["safety_backup_id"]
    db.close()

    reset_database_caches()
    titles = _live_titles()
    assert "marker-a" in titles
    assert "marker-b" not in titles
    db = get_session_factory()()
    try:
        from app.db.models import AuditEvent
        restore_audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "host_action.execute", AuditEvent.result == "success"))
        assert restore_audit is not None
    finally:
        db.close()


def test_restore_from_encrypted_artifact(configured_app) -> None:
    """An encrypted off-host artifact restores when the key is configured."""
    _bootstrap()
    settings = get_settings()
    key = os.urandom(32).hex()
    destination = settings.data_dir / "off-host"
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    _add_task(db, user.id, "marker-a")
    record = create_backup(settings.data_dir, settings.database_url, user.id, db)
    assert record.status == "verified"
    artifact = destination / "encrypted" / f"{record.id}.nxb"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    encrypt_file(settings.data_dir / record.relative_path, artifact, key)
    record.encryption_status = "encrypted"
    record.encrypted_relative_path = f"encrypted/{record.id}.nxb"
    db.commit()
    _add_task(db, user.id, "marker-b")
    record = db.get(BackupRecord, record.id)
    result = restore_backup(settings.data_dir, settings.database_url, record, db, replication_destination=destination, encryption_key=key)
    assert result["restart_required"] is True
    db.close()

    reset_database_caches()
    titles = _live_titles()
    assert "marker-a" in titles
    assert "marker-b" not in titles


def test_restore_rejects_tampered_encrypted_artifact(configured_app) -> None:
    """A tampered encrypted artifact never reaches the live database."""
    _bootstrap()
    settings = get_settings()
    key = os.urandom(32).hex()
    destination = settings.data_dir / "off-host"
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    _add_task(db, user.id, "marker-a")
    record = create_backup(settings.data_dir, settings.database_url, user.id, db)
    artifact = destination / "encrypted" / f"{record.id}.nxb"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    encrypt_file(settings.data_dir / record.relative_path, artifact, key)
    record.encryption_status = "encrypted"
    record.encrypted_relative_path = f"encrypted/{record.id}.nxb"
    db.commit()
    with artifact.open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(RestoreError):
        restore_backup(settings.data_dir, settings.database_url, record, db, replication_destination=destination, encryption_key=key)
    db.close()
    assert "marker-a" in _live_titles()


def test_restore_rejects_unverified_source(configured_app) -> None:
    """Only verified records are restorable; nothing is touched otherwise."""
    _bootstrap()
    settings = get_settings()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    record = BackupRecord(user_id=user.id, relative_path="backups/x.db", size_bytes=1, sha256="0" * 64, status="failed", integrity_result="failed")
    db.add(record)
    db.commit()
    try:
        with pytest.raises(RestoreError):
            restore_backup(settings.data_dir, settings.database_url, record, db)
    finally:
        db.close()


def test_restore_rejects_tampered_local_backup(configured_app) -> None:
    """A digest mismatch aborts before any swap occurs."""
    _bootstrap()
    settings = get_settings()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    _add_task(db, user.id, "marker-a")
    record = create_backup(settings.data_dir, settings.database_url, user.id, db)
    path = settings.data_dir / record.relative_path
    with path.open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(RestoreError):
        restore_backup(settings.data_dir, settings.database_url, record, db)
    db.close()
    assert "marker-a" in _live_titles()


def test_restore_failed_source_resolution_creates_no_safety_backup(configured_app) -> None:
    """A restore that cannot resolve its source leaves no spurious backup behind."""
    _bootstrap()
    settings = get_settings()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    _add_task(db, user.id, "marker-a")
    record = create_backup(settings.data_dir, settings.database_url, user.id, db)
    record.encryption_status = "encrypted"
    record.encrypted_relative_path = f"encrypted/{record.id}.nxb"
    db.commit()
    count_before = len(db.scalars(select(BackupRecord)).all())
    with pytest.raises(RestoreError):
        restore_backup(settings.data_dir, settings.database_url, record, db)
    db.close()

    db = get_session_factory()()
    try:
        count_after = len(db.scalars(select(BackupRecord)).all())
    finally:
        db.close()
    assert count_after == count_before
    assert "marker-a" in _live_titles()


def test_restore_rolls_back_when_post_swap_check_fails(configured_app, monkeypatch) -> None:
    """A failed final verification rolls back to the pre-restore safety backup."""
    import app.modules.host_actions.restore as restore_module

    _bootstrap()
    settings = get_settings()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    _add_task(db, user.id, "marker-a")
    record = create_backup(settings.data_dir, settings.database_url, user.id, db)
    _add_task(db, user.id, "marker-b")
    record = db.get(BackupRecord, record.id)

    original_integrity = restore_module._integrity
    calls = {"count": 0}

    def failing_live_integrity(path) -> str:
        calls["count"] += 1
        if calls["count"] >= 3:
            return "not ok"
        return original_integrity(path)

    monkeypatch.setattr(restore_module, "_integrity", failing_live_integrity)
    with pytest.raises(RestoreError):
        restore_backup(settings.data_dir, settings.database_url, record, db)
    db.close()

    reset_database_caches()
    titles = _live_titles()
    # The restore source contains only marker-a; the safety backup contains
    # both, so marker-b present proves the live database was rolled back.
    assert "marker-a" in titles
    assert "marker-b" in titles


def test_restore_proposal_flow_via_api(client) -> None:
    """Restore is a high-risk proposal that only executes after explicit confirmation."""
    _bootstrap()
    _login(client)
    csrf = _csrf(client)
    settings = get_settings()

    created = client.post(
        "/api/v1/system/actions/proposals",
        json={"action_key": "maintenance.create_backup", "input": {}},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "create-b"},
    )
    assert created.status_code == 201
    confirmed = client.post(f"/api/v1/system/actions/proposals/{created.json()['id']}/confirm", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "create-b-confirm"})
    assert confirmed.status_code == 200
    db = get_session_factory()()
    try:
        assert process_host_actions(db, data_dir=settings.data_dir, database_url=settings.database_url) == 1
    finally:
        db.close()
    backups = client.get("/api/v1/system/backups").json()
    assert len(backups) == 1
    assert backups[0]["status"] == "verified"
    backup_id = backups[0]["id"]

    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    _add_task(db, user.id, "marker-b")
    db.close()

    restore = client.post(
        "/api/v1/system/actions/proposals",
        json={"action_key": "maintenance.restore_backup", "input": {"backup_id": backup_id}},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "restore-propose"},
    )
    assert restore.status_code == 201
    assert restore.json()["risk_level"] == "high"
    blocked = client.post(f"/api/v1/system/actions/proposals/{restore.json()['id']}/confirm")
    assert blocked.status_code == 403
    queued = client.post(f"/api/v1/system/actions/proposals/{restore.json()['id']}/confirm", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "restore-confirm"})
    assert queued.status_code == 200
    assert queued.json()["status"] == "queued"

    db = get_session_factory()()
    try:
        assert process_host_actions(db, data_dir=settings.data_dir, database_url=settings.database_url) == 1
    finally:
        db.close()

    reset_database_caches()
    titles = _live_titles()
    assert "marker-b" not in titles
    # The restored snapshot has no post-backup rows; the durable evidence of
    # the restore lives in the restored database's own audit history.
    audit = client.get("/api/v1/system/audit").json()["items"]
    assert any(item["action"] == "host_action.execute" and item["result"] == "success" for item in audit)
