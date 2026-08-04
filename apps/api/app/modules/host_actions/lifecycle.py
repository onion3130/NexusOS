"""Backup retention policy, pruning, and encryption key rotation.

Retention and rotation are catalogued maintenance actions that only ever run in
the worker after an explicit, typed, user-confirmed proposal. The policy is
server-configured (``BACKUP_RETENTION_COUNT`` / ``BACKUP_RETENTION_DAYS``);
clients never select which backups to delete. The newest verified backup is
always retained, and artifacts are only deleted when their digest still matches
the trusted record so tampered material is never silently destroyed. Rotation
keys are environment-only and never cross the API.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.db.models import BackupRecord
from app.modules.backup_replication.encryption import EncryptionError, decrypt_file, encrypt_file, verify_file
from app.modules.host_actions.backups import _hash_file
from app.modules.identity.service import add_audit_event


class LifecycleError(ValueError):
    """Raised when a lifecycle operation cannot proceed safely."""


def retention_policy(
    records: list[BackupRecord],
    *,
    retention_count: int,
    retention_days: int,
    now: datetime | None = None,
) -> tuple[list[BackupRecord], list[BackupRecord]]:
    """Return ``(to_prune, retained)`` under the configured policy.

    Only ``verified`` records are considered. The newest ``retention_count``
    and every record younger than ``retention_days`` are retained; the newest
    record is always retained (last-backup protection), so a retention run can
    never leave the operator without a verified recovery point.
    """
    current = now or datetime.now(UTC)
    verified = sorted(
        [record for record in records if record.status == "verified"],
        key=lambda item: item.created_at,
        reverse=True,
    )
    if not verified:
        return [], []
    cutoff = current - timedelta(days=retention_days)
    retained: set[str] = set()
    for index, record in enumerate(verified):
        created = record.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if index < max(1, retention_count) or created >= cutoff:
            retained.add(record.id)
    # Index 0 is always below ``max(1, retention_count)``, so the newest
    # verified backup is always retained and the retained set is never empty.
    return [record for record in verified if record.id not in retained], [record for record in verified if record.id in retained]


def _local_artifact(root: Path, relative_path: str) -> Path:
    """Resolve one local backup artifact strictly beneath the data volume."""
    path = (root / relative_path).resolve()
    if root not in path.parents or path.suffix != ".db":
        raise LifecycleError("backup_path_invalid")
    return path


def _remote_artifact(destination: Path, relative_path: str) -> Path:
    """Resolve one encrypted artifact strictly beneath the replication root."""
    dest_root = destination.expanduser().resolve()
    path = (dest_root / relative_path).resolve()
    if dest_root not in path.parents or path.suffix != ".nxb":
        raise LifecycleError("backup_path_invalid")
    return path


def prune_backups(
    data_dir: Path,
    db: OrmSession,
    records: list[BackupRecord],
    *,
    user_id: str,
    operation_id: str | None = None,
    replication_destination: Path | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Delete pruned artifacts and mark their records deleted with audit rows.

    A local artifact is deleted only when its SHA-256 still matches the trusted
    record; a digest mismatch is reported and skipped so unverifiable material
    is never silently destroyed. The record row is preserved (soft deletion)
    for audit continuity and the backup listing excludes deleted records.
    """
    root = data_dir.resolve()
    current = now or datetime.now(UTC)
    pruned = 0
    skipped = 0
    for record in records:
        try:
            # Validate every path and requirement before deleting anything so a
            # failed prune never destroys artifacts it cannot fully clean up.
            artifact = _local_artifact(root, record.relative_path)
            remote: Path | None = None
            if record.encryption_status == "encrypted" and record.encrypted_relative_path:
                if replication_destination is None:
                    raise LifecycleError("retention_encrypted_destination_unavailable")
                remote = _remote_artifact(replication_destination, record.encrypted_relative_path)
            if artifact.is_file():
                try:
                    if _hash_file(artifact) != record.sha256:
                        skipped += 1
                        continue
                except OSError:
                    skipped += 1
                    continue
                artifact.unlink(missing_ok=True)
            if remote is not None and remote.is_file():
                remote.unlink(missing_ok=True)
            record.status = "deleted"
            record.pruned_at = current
            if record.replication_status == "replicated":
                record.replication_status = "deleted"
            add_audit_event(
                db,
                action="backup_retention.prune",
                result="success",
                actor_user_id=user_id,
                target=record.id,
                metadata={"relative_path": record.relative_path, "job_id": operation_id},
            )
            pruned += 1
        except (OSError, LifecycleError) as exc:
            if isinstance(exc, LifecycleError):
                raise
            raise LifecycleError("retention_prune_failed") from exc
    db.flush()
    return {"pruned": pruned, "skipped": skipped}


def rotate_encryption_keys(
    *,
    db: OrmSession,
    user_id: str,
    destination: Path | None,
    current_key: str | None,
    previous_key: str | None,
    operation_id: str | None = None,
) -> dict[str, object]:
    """Re-encrypt every replicated artifact from the previous key to the current key.

    Both keys must be configured and differ. Each artifact is verified against
    the current key first so an interrupted rotation can be retried
    idempotently. Artifacts are decrypted to a bounded staging file, re-encrypted
    to a temporary artifact, authenticated with the current key, and atomically
    replaced; plaintext staging and temporary ciphertext are always removed.
    """
    if destination is None or not current_key or not previous_key:
        raise LifecycleError("rotation_keys_unavailable")
    if current_key == previous_key:
        raise LifecycleError("rotation_keys_identical")
    records = db.scalars(
        select(BackupRecord).where(BackupRecord.encryption_status == "encrypted", BackupRecord.replication_status == "replicated")
    ).all()
    rotated = 0
    for record in records:
        if not record.encrypted_relative_path:
            continue
        artifact = _remote_artifact(destination, record.encrypted_relative_path)
        if not artifact.is_file():
            raise LifecycleError("rotation_artifact_missing")
        try:
            verify_file(artifact, current_key)
            continue  # already rotated under the current key; safe retry
        except EncryptionError:
            pass
        staging = artifact.with_name(artifact.name + ".rotate-staging")
        temporary = artifact.with_name(artifact.name + ".tmp")
        try:
            staging.unlink(missing_ok=True)
            temporary.unlink(missing_ok=True)
            decrypt_file(artifact, staging, previous_key)
            if _hash_file(staging) != record.sha256:
                raise LifecycleError("rotation_digest_mismatch")
            _, _ = encrypt_file(staging, temporary, current_key)
            size, digest = verify_file(temporary, current_key)
            temporary.replace(artifact)
            record.encrypted_sha256 = digest
            record.encrypted_size_bytes = size
            add_audit_event(
                db,
                action="backup_replication.rotate",
                result="success",
                actor_user_id=user_id,
                target=record.id,
                metadata={"job_id": operation_id},
            )
            rotated += 1
        except (OSError, EncryptionError, LifecycleError) as exc:
            temporary.unlink(missing_ok=True)
            staging.unlink(missing_ok=True)
            if isinstance(exc, LifecycleError):
                raise
            raise LifecycleError("rotation_failed") from exc
        finally:
            temporary.unlink(missing_ok=True)
            staging.unlink(missing_ok=True)
    db.flush()
    return {"rotated": rotated}
