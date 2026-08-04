"""Provider-neutral encrypted backup replication over an operator-mounted directory."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session as OrmSession

from app.db.base import utc_now
from app.db.models import BackupRecord, Job
from app.modules.identity.service import add_audit_event
from app.modules.backup_replication.encryption import EncryptionError, encrypt_file, verify_file

MAX_ATTEMPTS = 3
LEASE = timedelta(minutes=5)


class ReplicationError(ValueError):
    """Raised when an encrypted backup cannot be replicated safely."""


class ReplicationAdapter(Protocol):
    """Small interface that future object-storage adapters can implement."""

    def replicate(self, source: Path, object_name: str, encryption_key: str) -> tuple[str, int, str]:
        """Encrypt and persist one source artifact, returning metadata."""


class DirectoryReplicationAdapter:
    """Replicate encrypted artifacts to an operator-mounted destination root."""

    def __init__(self, destination: Path, data_dir: Path) -> None:
        self.destination = destination.expanduser().resolve()
        self.data_dir = data_dir.expanduser().resolve()
        if self.destination == self.data_dir or self.data_dir in self.destination.parents or self.destination in self.data_dir.parents:
            raise ReplicationError("replication_destination_must_be_off_host")

    def replicate(self, source: Path, object_name: str, encryption_key: str) -> tuple[str, int, str]:
        """Write an authenticated encrypted artifact atomically beneath destination."""
        source = source.expanduser().resolve()
        if self.data_dir not in source.parents or not source.is_file():
            raise ReplicationError("backup_source_invalid")
        relative = Path("encrypted") / f"{object_name}.nxb"
        destination = (self.destination / relative).resolve()
        if self.destination not in destination.parents:
            raise ReplicationError("replication_destination_invalid")
        temporary = destination.with_suffix(".tmp")
        try:
            destination.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
            temporary.unlink(missing_ok=True)
            _, _ = encrypt_file(source, temporary, encryption_key)
            size, digest = verify_file(temporary, encryption_key)
            temporary.replace(destination)
            return str(relative), destination.stat().st_size, digest
        except (OSError, EncryptionError) as exc:
            temporary.unlink(missing_ok=True)
            if isinstance(exc, ReplicationError):
                raise
            raise ReplicationError("replication_write_failed") from exc


def _record_id(job: Job) -> str | None:
    """Read one bounded backup ID from a replication job payload."""
    try:
        value = json.loads(job.payload_json or "{}").get("backup_id")
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, str) and value else None


def queue_replication(db: OrmSession, record: BackupRecord) -> None:
    """Queue exactly one replication job for a verified local backup."""
    existing = db.scalar(select(Job).where(Job.idempotency_key == f"backup-replication:{record.id}"))
    if existing is None:
        db.add(Job(job_type="backup_replication", status="queued", payload_json=json.dumps({"backup_id": record.id}, separators=(",", ":")), available_at=utc_now(), idempotency_key=f"backup-replication:{record.id}"))
    record.replication_status = "queued"
    record.replication_error_code = None
    db.flush()


def _claim(db: OrmSession, current: datetime) -> str | None:
    """Claim one queued or expired replication job."""
    candidate = db.scalar(select(Job.id).where(Job.job_type == "backup_replication", Job.attempts < MAX_ATTEMPTS, Job.available_at <= current, or_(Job.status == "queued", (Job.status == "processing") & (Job.locked_until <= current))).order_by(Job.created_at).limit(1))
    if candidate is None:
        return None
    result = db.execute(update(Job).where(Job.id == candidate, Job.attempts < MAX_ATTEMPTS, or_(Job.status == "queued", (Job.status == "processing") & (Job.locked_until <= current))).values(status="processing", attempts=Job.attempts + 1, locked_until=current + LEASE, started_at=current))
    db.commit()
    return candidate if result.rowcount == 1 else None


def _hash_file(path: Path) -> str:
    """Hash a local artifact in bounded reads."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fail_exhausted(db: OrmSession, current: datetime) -> None:
    """Terminally fail stale replication leases after the retry limit."""
    jobs = db.scalars(select(Job).where(Job.job_type == "backup_replication", Job.status == "processing", Job.locked_until <= current, Job.attempts >= MAX_ATTEMPTS)).all()
    for job in jobs:
        record = db.get(BackupRecord, _record_id(job)) if _record_id(job) else None
        if record is not None:
            record.replication_status = "failed"
            record.replication_error_code = "worker_retry_limit"
        job.status = "failed"
        job.last_error_code = "worker_retry_limit"
        job.locked_until = None
        job.completed_at = current
        if record is not None:
            add_audit_event(db, action="backup_replication.execute", result="failure", actor_user_id=record.user_id, target=record.id, metadata={"error": "worker_retry_limit", "job_id": job.id})
    if jobs:
        db.commit()


def process_replication_jobs(db: OrmSession, *, data_dir: Path, destination: Path | None, encryption_key: str | None, now: datetime | None = None, batch_size: int = 2) -> int:
    """Process a bounded replication batch without affecting reminder delivery."""
    if destination is None or not encryption_key:
        return 0
    current = now or utc_now()
    _fail_exhausted(db, current)
    processed = 0
    for _ in range(max(1, min(batch_size, 5))):
        job_id = _claim(db, current)
        if job_id is None:
            break
        job = db.get(Job, job_id)
        record = db.get(BackupRecord, _record_id(job) if job else "") if job else None
        if job is None or record is None or record.status != "verified":
            if job is not None:
                job.status = "failed"
                job.last_error_code = "backup_unavailable"
                job.locked_until = None
                job.completed_at = current
                db.commit()
            processed += 1
            continue
        record.replication_status = "processing"
        db.commit()
        try:
            source = (data_dir.resolve() / record.relative_path).resolve()
            if _hash_file(source) != record.sha256:
                raise ReplicationError("backup_digest_mismatch")
            adapter = DirectoryReplicationAdapter(destination, data_dir)
            relative, size, digest = adapter.replicate(source, record.id, encryption_key)
            record.encryption_status = "encrypted"
            record.encrypted_relative_path = relative
            record.encrypted_size_bytes = size
            record.encrypted_sha256 = digest
            record.replication_status = "replicated"
            record.replicated_at = current
            record.replication_error_code = None
            job.status = "completed"
            job.locked_until = None
            job.completed_at = current
            add_audit_event(db, action="backup_replication.execute", result="success", actor_user_id=record.user_id, target=record.id, metadata={"job_id": job.id})
        except (OSError, ReplicationError, EncryptionError) as exc:
            code = str(exc) or "replication_failed"
            record.replication_status = "queued" if job.attempts < MAX_ATTEMPTS else "failed"
            record.replication_error_code = code
            job.status = "queued" if job.attempts < MAX_ATTEMPTS else "failed"
            job.available_at = current + timedelta(seconds=30 * job.attempts)
            job.last_error_code = code
            job.locked_until = None
            if job.status == "failed":
                job.completed_at = current
                add_audit_event(db, action="backup_replication.execute", result="failure", actor_user_id=record.user_id, target=record.id, metadata={"job_id": job.id, "error": code})
        db.commit()
        processed += 1
    return processed
