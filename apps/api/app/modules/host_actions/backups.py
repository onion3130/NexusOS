"""SQLite backup and integrity operations with fixed NexusOS paths."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.db.models import BackupRecord


class BackupError(ValueError):
    """Raised when a backup cannot be created or verified safely."""


def database_path(database_url: str, data_dir: Path | None = None) -> Path:
    """Resolve the supported SQLite file path within the configured data volume."""
    if not database_url.startswith("sqlite:///"):
        raise BackupError("sqlite_database_required")
    value = database_url.removeprefix("sqlite:///")
    if not value or value == ":memory:":
        raise BackupError("file_database_required")
    path = Path(value).resolve()
    if not path.is_file():
        raise BackupError("database_file_missing")
    if data_dir is not None:
        root = data_dir.resolve()
        if root not in path.parents or path.parent == (root / "backups").resolve():
            raise BackupError("database_path_invalid")
    return path


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integrity(path: Path) -> str:
    """Return SQLite's safe integrity result without exposing database content."""
    connection = None
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        result = connection.execute("PRAGMA integrity_check").fetchone()
        return str(result[0]) if result else "unknown"
    except sqlite3.Error:
        return "failed"
    finally:
        if connection is not None:
            connection.close()


def create_backup(
    data_dir: Path,
    database_url: str,
    user_id: str,
    db,
    operation_id: str | None = None,
) -> BackupRecord:
    """Create or recover one uniquely identified hot backup in `DATA_DIR/backups`."""
    root = data_dir.resolve()
    source_path = database_path(database_url, root)
    backup_dir = root / "backups"
    backup_dir.mkdir(mode=0o750, parents=True, exist_ok=True)
    suffix = operation_id or uuid4().hex
    safe_suffix = "".join(character for character in suffix if character.isalnum() or character in "-_")[:64]
    filename = f"nexus-{safe_suffix}.db"
    destination = backup_dir / filename
    relative_path = str(destination.relative_to(root))

    existing = db.scalar(select(BackupRecord).where(BackupRecord.relative_path == relative_path))
    if existing is not None and existing.status == "verified":
        # A durable record is not proof that the file still exists or has not
        # been tampered with. Revalidate every retry before returning success.
        try:
            if verify_backup(root, existing).status == "verified":
                return existing
        except BackupError:
            pass
    if existing is not None:
        db.delete(existing)
        db.flush()
        destination.unlink(missing_ok=True)
    elif destination.exists():
        # A process can die after creating the file but before recording it.
        # Never treat a partial artifact as a valid retry result.
        destination.unlink(missing_ok=True)

    if not destination.exists():
        source = None
        target = None
        try:
            source = sqlite3.connect(source_path)
            target = sqlite3.connect(destination)
            source.backup(target, pages=256, sleep=0.05)
            target.execute("PRAGMA wal_checkpoint(PASSIVE)")
            target.commit()
        except (OSError, sqlite3.Error) as exc:
            destination.unlink(missing_ok=True)
            raise BackupError("backup_failed") from exc
        finally:
            if target is not None:
                target.close()
            if source is not None:
                source.close()

    integrity = _integrity(destination)
    try:
        digest = _hash_file(destination)
        size_bytes = destination.stat().st_size
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise BackupError("backup_verification_failed") from exc
    record = BackupRecord(
        user_id=user_id,
        relative_path=relative_path,
        size_bytes=size_bytes,
        sha256=digest,
        status="verified" if integrity == "ok" else "failed",
        integrity_result=integrity,
        verified_at=datetime.now(UTC) if integrity == "ok" else None,
    )
    db.add(record)
    db.flush()
    return record


def verify_backup(data_dir: Path, record: BackupRecord) -> BackupRecord:
    """Verify path containment, SQLite integrity, and the recorded content digest."""
    root = data_dir.resolve()
    path = (root / record.relative_path).resolve()
    if root not in path.parents or path.suffix != ".db" or not path.is_file():
        raise BackupError("backup_path_invalid")
    integrity = _integrity(path)
    try:
        digest = _hash_file(path)
        size_bytes = path.stat().st_size
    except OSError as exc:
        raise BackupError("backup_unavailable") from exc
    digest_matches = digest == record.sha256
    record.integrity_result = integrity if digest_matches else "digest_mismatch"
    record.status = "verified" if integrity == "ok" and digest_matches else "failed"
    record.verified_at = datetime.now(UTC) if record.status == "verified" else None
    record.size_bytes = size_bytes
    # Preserve the original digest so a tampered file cannot become trusted
    # merely by calling the verification endpoint again.
    return record
