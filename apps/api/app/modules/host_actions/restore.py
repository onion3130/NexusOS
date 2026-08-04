"""Confirmation-gated restore from verified NexusOS backup artifacts.

Restore is the highest-risk catalogued operation. It only ever runs in the
worker after an explicit, typed, user-confirmed proposal. The live database is
never replaced until the source resolves, a fresh verified safety backup
exists, the staged source passes both SHA-256 and SQLite integrity checks, and
the swap is atomic with a rollback to the safety backup if the replacement or
the final verification fails.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.db.models import BackupRecord
from app.modules.backup_replication.encryption import EncryptionError, decrypt_file
from app.modules.host_actions.backups import BackupError, _hash_file, _integrity, create_backup, database_path

STAGING_SUFFIX = ".restore-staging"
_COPY_CHUNK = 1024 * 1024


class RestoreError(ValueError):
    """Raised when a restore cannot proceed safely."""


def _stage_path(live: Path) -> Path:
    return live.with_name(live.name + STAGING_SUFFIX)


def _copy_file(source: Path, destination: Path) -> None:
    """Copy one artifact in bounded reads and flush it to disk."""
    with source.open("rb") as input_stream, destination.open("wb") as output_stream:
        while True:
            chunk = input_stream.read(_COPY_CHUNK)
            if not chunk:
                break
            output_stream.write(chunk)
        output_stream.flush()
        os.fsync(output_stream.fileno())


def _remove_sidecars(live: Path) -> None:
    """Drop stale journal sidecars so a restored database starts cleanly."""
    for suffix in ("-wal", "-shm", "-journal"):
        live.with_name(live.name + suffix).unlink(missing_ok=True)


def _resolve_source(root: Path, destination: Path | None, record: BackupRecord, encryption_key: str | None) -> Path:
    """Resolve the restore source server-side; client input never selects paths."""
    if record.encryption_status == "encrypted":
        if not record.encrypted_relative_path or destination is None or not encryption_key:
            raise RestoreError("restore_key_unavailable")
        dest_root = destination.expanduser().resolve()
        source = (dest_root / record.encrypted_relative_path).resolve()
        if dest_root not in source.parents or not source.is_file():
            raise RestoreError("restore_source_invalid")
        return source
    if not record.relative_path:
        raise RestoreError("restore_source_invalid")
    source = (root / record.relative_path).resolve()
    if root not in source.parents or not source.is_file():
        raise RestoreError("restore_source_invalid")
    return source


def _stage(source: Path, staging: Path, record: BackupRecord, encryption_key: str | None) -> None:
    """Materialize a verified staging copy (decrypting encrypted artifacts)."""
    if record.encryption_status == "encrypted":
        _total, digest = decrypt_file(source, staging, encryption_key)
        if digest != record.sha256:
            raise RestoreError("restore_digest_mismatch")
    else:
        _copy_file(source, staging)
        if _hash_file(staging) != record.sha256:
            raise RestoreError("restore_digest_mismatch")


def _record_restore_marker(staging: Path, record: BackupRecord, restored_at: datetime) -> None:
    """Record the restore timestamp inside the staged database when supported.

    Backups created before migration ``0010_restore`` do not have the column;
    they remain fully restorable and the marker is simply skipped.
    """
    try:
        connection = sqlite3.connect(staging)
        try:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(backup_records)")}
            if "restored_at" not in columns:
                return
            connection.execute(
                "UPDATE backup_records SET restored_at = ? WHERE id = ?",
                (restored_at.strftime("%Y-%m-%d %H:%M:%S.%f"), record.id),
            )
            connection.commit()
        finally:
            connection.close()
    except sqlite3.Error:
        return


def _record_restore_audit(staging: Path, record: BackupRecord, restored_at: datetime, operation_id: str | None) -> None:
    """Persist a restore audit row inside the staged database when supported.

    A restored database should describe its own restoration even after the
    API/worker restart, independent of the superseded pre-restore database.
    Older backups without the audit schema are still fully restorable.
    """
    try:
        connection = sqlite3.connect(staging)
        try:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(audit_events)")}
            if not {"id", "actor_user_id", "action", "target", "result", "metadata_json", "created_at"}.issubset(columns):
                return
            metadata = json.dumps({"backup_id": record.id, "job_id": operation_id, "restored_at": restored_at.isoformat()}, separators=(",", ":"))
            connection.execute(
                "INSERT INTO audit_events (id, actor_user_id, action, target, result, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid4()), record.user_id, "host_action.execute", record.id, "success", metadata, restored_at.strftime("%Y-%m-%d %H:%M:%S.%f")),
            )
            connection.commit()
        finally:
            connection.close()
    except sqlite3.Error:
        return


def restore_backup(
    data_dir: Path,
    database_url: str,
    record: BackupRecord,
    db,
    *,
    operation_id: str | None = None,
    replication_destination: Path | None = None,
    encryption_key: str | None = None,
) -> dict[str, object]:
    """Restore one verified backup over the live database with safety and atomicity."""
    root = data_dir.resolve()
    live = database_path(database_url, root)
    if record.status != "verified":
        raise RestoreError("restore_source_not_verified")

    # Validate the restore source before creating anything: a failed restore
    # attempt (missing artifact, unconfigured key) must not leave a spurious
    # safety-backup record behind.
    source = _resolve_source(root, replication_destination, record, encryption_key)

    staging = _stage_path(live)
    staging.unlink(missing_ok=True)
    restored_at = datetime.now(UTC)
    try:
        # 1. Pre-restore safety backup: a verified SQLite snapshot for rollback.
        safety = create_backup(root, database_url, record.user_id, db)
        if safety.status != "verified":
            raise RestoreError("restore_safety_backup_failed")

        def _rollback_to_safety() -> None:
            """Replace the live database with the pre-restore safety backup."""
            try:
                safety_path = (root / safety.relative_path).resolve()
                os.replace(safety_path, live)
                _remove_sidecars(live)
            except OSError:
                pass

        # 2. Stage and verify the restore source before anything is replaced.
        _stage(source, staging, record, encryption_key)
        if _integrity(staging) != "ok":
            raise RestoreError("restore_integrity_failed")
        _record_restore_marker(staging, record, restored_at)
        _record_restore_audit(staging, record, restored_at, operation_id)
        if _integrity(staging) != "ok":
            raise RestoreError("restore_integrity_failed")

        # 3. Release every open handle so the live file can be replaced on all
        # platforms (Windows cannot replace a file another process has open).
        db.commit()
        from app.db.session import get_engine

        get_engine().dispose()

        # 4. Atomic swap, rolling back to the safety backup if the swap itself
        # fails or the restored file fails its final verification.
        try:
            os.replace(staging, live)
        except OSError as exc:
            _rollback_to_safety()
            raise RestoreError("restore_swap_failed") from exc
        _remove_sidecars(live)
        if _integrity(live) != "ok":
            _rollback_to_safety()
            raise RestoreError("restore_post_check_failed")
    except RestoreError:
        staging.unlink(missing_ok=True)
        raise
    except (OSError, BackupError, EncryptionError) as exc:
        staging.unlink(missing_ok=True)
        raise RestoreError("restore_failed") from exc

    return {
        "backup_id": record.id,
        "safety_backup_id": safety.id,
        "restored_at": restored_at.isoformat(),
        "restart_required": True,
    }
