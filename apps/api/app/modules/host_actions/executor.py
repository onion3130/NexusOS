"""Fixed host-action adapters; arbitrary shell and privileged host control are absent."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session as OrmSession

from app.db.models import BackupRecord
from app.modules.host_actions.backups import create_backup, verify_backup


def execute_action(
    action_key: str,
    action_input: dict[str, object],
    *,
    data_dir: Path,
    database_url: str,
    user_id: str,
    db: OrmSession,
    operation_id: str | None = None,
) -> dict[str, object]:
    """Execute one catalogued operation using fixed Python/SQLite APIs."""
    if action_key == "maintenance.create_backup":
        record = create_backup(data_dir, database_url, user_id, db, operation_id=operation_id)
        if record.status != "verified":
            raise ValueError("backup_verification_failed")
        return {"backup_id": record.id, "status": record.status, "relative_path": record.relative_path}
    if action_key == "maintenance.verify_backup":
        backup_id = action_input.get("backup_id")
        record = db.get(BackupRecord, backup_id)
        if record is None or record.user_id != user_id:
            raise ValueError("backup_not_found")
        record = verify_backup(data_dir, record)
        if record.status != "verified":
            raise ValueError("backup_verification_failed")
        return {"backup_id": record.id, "status": record.status, "integrity_result": record.integrity_result}
    if action_key == "maintenance.integrity_check":
        result = db.execute(text("PRAGMA integrity_check")).scalar()
        if result != "ok":
            raise ValueError("database_integrity_failed")
        return {"status": "ok", "integrity_result": "ok"}
    raise ValueError("action_not_allowed")
