"""Milestone 10 encrypted backup replication tests."""

from __future__ import annotations

from pathlib import Path
import hashlib

import pytest

from app.modules.backup_replication.encryption import CHUNK_SIZE, EncryptionError, encrypt_file, verify_file
from app.db.models import BackupRecord, User
from app.db.session import get_session_factory
from app.modules.backup_replication.replicator import DirectoryReplicationAdapter, ReplicationError, process_replication_jobs, queue_replication
from app.modules.identity.service import bootstrap_owner
from app.core.config import get_settings

KEY = "0123456789abcdef" * 4


def test_chunked_encryption_authenticates_and_detects_tampering(tmp_path: Path) -> None:
    """Encrypted artifacts verify with the key and fail closed after tampering."""
    source = tmp_path / "source.db"
    encrypted = tmp_path / "encrypted.nxb"
    source.write_bytes(b"nexus backup payload\n" * 100_000)
    size, digest = encrypt_file(source, encrypted, KEY)
    assert size == source.stat().st_size
    assert len(digest) == 64
    assert verify_file(encrypted, KEY) == (size, digest)
    raw = bytearray(encrypted.read_bytes())
    raw[-1] ^= 1
    encrypted.write_bytes(raw)
    with pytest.raises(EncryptionError, match="encrypted_backup_invalid"):
        verify_file(encrypted, KEY)

    encrypt_file(source, encrypted, KEY)
    framed = bytearray(encrypted.read_bytes())
    framed[len(b"NEXUS-BKP-2\\n")] ^= 1
    encrypted.write_bytes(framed)
    with pytest.raises(EncryptionError, match="encrypted_backup_invalid"):
        verify_file(encrypted, KEY)

    encrypt_file(source, encrypted, KEY)
    truncated = encrypted.read_bytes()[:-CHUNK_SIZE]
    encrypted.write_bytes(truncated)
    with pytest.raises(EncryptionError, match="encrypted_backup_invalid"):
        verify_file(encrypted, KEY)


def test_directory_adapter_rejects_in_volume_destination(tmp_path: Path) -> None:
    """Replication cannot silently write encrypted copies beside the source database."""
    with pytest.raises(ReplicationError, match="off_host"):
        DirectoryReplicationAdapter(tmp_path / "backups", tmp_path)


def test_directory_adapter_replicates_atomically(tmp_path: Path) -> None:
    """The operator-mounted destination receives a verified encrypted artifact."""
    data_dir = tmp_path / "data"
    destination = tmp_path.parent / f"{tmp_path.name}-off-host"
    source = data_dir / "backups" / "source.db"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"sqlite-like backup")
    adapter = DirectoryReplicationAdapter(destination, data_dir)
    relative, size, digest = adapter.replicate(source, "backup-1", KEY)
    artifact = destination / relative
    assert artifact.is_file()
    assert size == artifact.stat().st_size
    assert len(digest) == 64
    assert verify_file(artifact, KEY)[0] == source.stat().st_size
    assert not list(destination.rglob("*.tmp"))
    import shutil
    shutil.rmtree(destination, ignore_errors=True)


def test_replication_worker_processes_durable_job(configured_app, tmp_path: Path) -> None:
    """A queued backup replication job is leased, encrypted, verified, and completed."""
    settings = get_settings()
    db = get_session_factory()()
    destination = tmp_path.parent / f"{tmp_path.name}-worker-off-host"
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
        user = db.query(User).filter(User.username == "owner").one()
        source = settings.data_dir / "backups" / "worker.db"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"durable backup")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        record = BackupRecord(user_id=user.id, relative_path="backups/worker.db", size_bytes=source.stat().st_size, sha256=digest, status="verified", integrity_result="ok")
        db.add(record)
        db.flush()
        queue_replication(db, record)
        db.commit()
        assert process_replication_jobs(db, data_dir=settings.data_dir, destination=destination, encryption_key=KEY) == 1
        db.refresh(record)
        assert record.replication_status == "replicated"
        assert record.encryption_status == "encrypted"
        assert (destination / record.encrypted_relative_path).is_file()
    finally:
        db.close()
        import shutil
        shutil.rmtree(destination, ignore_errors=True)
