"""Approved-root source synchronization services."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.core.config import Settings
from app.db.base import utc_now
from app.db.models import Job, Source, SourceSyncConfig
from app.modules.identity.service import add_audit_event
from app.modules.sources.service import (
    _read_approved_file,
    _source_root,
    _job_for_source,
    _approved_roots,
    discover_approved_files,
)

SYNC_JOB_TYPE = "source_sync"
DEFAULT_INTERVAL_SECONDS = 3600
MIN_INTERVAL_SECONDS = 900
MAX_INTERVAL_SECONDS = 86400
MAX_BATCH_SIZE = 4
MAX_ATTEMPTS = 3
LEASE_SECONDS = 180


def _aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


def _next_check(now: datetime, interval_seconds: int) -> datetime:
    return now + timedelta(seconds=interval_seconds)


def _resolve_sync_file(settings: Settings, config: SourceSyncConfig) -> tuple[Path, dict[str, object]] | None:
    """Resolve a configured approved file after a content change.

    The original opaque file ID includes the file digest, so it intentionally
    changes when the file changes. Root key and relative path are server-owned
    configuration, and the discovery scan revalidates confinement, extension,
    size, UTF-8 content, and symlink state before returning a candidate.
    """
    for item in discover_approved_files(settings, limit=100):
        if item["root_key"] == config.root_key and item["relative_path"] == config.relative_path:
            root_candidates = [
                (candidate_key, candidate_path)
                for candidate_key, candidate_path in _approved_roots(settings)
                if candidate_key == config.root_key
            ]
            if not root_candidates:
                return None
            root = root_candidates[0][1].resolve()
            candidate = (root / str(item["relative_path"])).resolve()
            if candidate != root and root in candidate.parents and candidate.is_file():
                return candidate, item
    return None


def sync_response(config: SourceSyncConfig | None) -> dict[str, object] | None:
    """Return bounded synchronization metadata without paths or file contents."""
    if config is None:
        return None
    return {
        "id": config.id,
        "enabled": config.enabled,
        "interval_seconds": config.interval_seconds,
        "last_checked_at": config.last_checked_at,
        "last_changed_at": config.last_changed_at,
        "last_success_at": config.last_success_at,
        "last_error_code": config.last_error_code,
        "next_check_at": config.next_check_at,
    }


def configure_sync(db: OrmSession, settings: Settings, user_id: str, source: Source, *, enabled: bool, interval_seconds: int) -> SourceSyncConfig:
    """Enable or update sync for an existing imported approved file."""
    if source.kind != "approved_file" or source.sync_config is None:
        raise ValueError("source_sync_requires_approved_file")
    if not MIN_INTERVAL_SECONDS <= interval_seconds <= MAX_INTERVAL_SECONDS:
        raise ValueError("invalid_sync_interval")
    config = source.sync_config
    resolved = _resolve_sync_file(settings, config)
    if resolved is None:
        raise ValueError("approved_file_not_found")
    config.enabled = enabled
    config.interval_seconds = interval_seconds
    config.next_check_at = utc_now() if enabled else None
    config.last_error_code = None
    add_audit_event(db, action="sources.sync.configure", result="success", actor_user_id=user_id, target=source.id, metadata={"enabled": enabled, "interval_seconds": interval_seconds})
    db.commit()
    db.refresh(config)
    return config


def disable_sync(db: OrmSession, user_id: str, source: Source) -> SourceSyncConfig | None:
    """Disable synchronization while retaining its bounded status history."""
    config = source.sync_config
    if config is None:
        return None
    config.enabled = False
    config.next_check_at = None
    config.last_error_code = None
    add_audit_event(db, action="sources.sync.disable", result="success", actor_user_id=user_id, target=source.id)
    db.commit()
    db.refresh(config)
    return config


def _enqueue_job(db: OrmSession, source_id: str, *, idempotency_key: str) -> Job:
    existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
    if existing is not None:
        return existing
    job = Job(job_type=SYNC_JOB_TYPE, status="queued", payload_json=source_id, available_at=utc_now(), idempotency_key=idempotency_key)
    db.add(job)
    db.flush()
    return job


def queue_manual_sync(db: OrmSession, user_id: str, source: Source) -> Job:
    """Queue one explicit sync check; reading remains worker-only."""
    if source.kind != "approved_file" or source.sync_config is None:
        raise ValueError("source_sync_requires_approved_file")
    job = _enqueue_job(db, source.id, idempotency_key=f"source-sync-manual:{source.id}:{uuid4()}")
    add_audit_event(db, action="sources.sync.request", result="success", actor_user_id=user_id, target=source.id)
    db.commit()
    db.refresh(job)
    return job


def enqueue_due_source_sync_jobs(db: OrmSession, *, now: datetime | None = None, batch_size: int = 2) -> int:
    """Schedule a bounded set of due synchronization checks."""
    current = now or datetime.now(UTC)
    configs = db.scalars(select(SourceSyncConfig).where(SourceSyncConfig.enabled.is_(True), SourceSyncConfig.next_check_at.is_not(None), SourceSyncConfig.next_check_at <= current).order_by(SourceSyncConfig.next_check_at, SourceSyncConfig.updated_at).limit(max(1, min(batch_size, MAX_BATCH_SIZE)))).all()
    queued = 0
    for config in configs:
        source = db.get(Source, config.source_id)
        if source is None or source.deleted_at is not None or source.status == "archived":
            config.enabled = False
            config.next_check_at = None
            continue
        slot = _aware(config.next_check_at) or current
        config.next_check_at = _next_check(current, config.interval_seconds)
        _enqueue_job(db, source.id, idempotency_key=f"source-sync-scheduled:{source.id}:{slot.isoformat()}")
        queued += 1
    if configs:
        db.commit()
    return queued


def _claim_jobs(db: OrmSession, *, now: datetime, batch_size: int) -> list[Job]:
    jobs = db.scalars(select(Job).where(Job.job_type == SYNC_JOB_TYPE, Job.status.in_(("queued", "processing")), Job.available_at <= now, Job.attempts < MAX_ATTEMPTS, (Job.locked_until.is_(None) | (Job.locked_until <= now))).order_by(Job.created_at).limit(max(1, min(batch_size, MAX_BATCH_SIZE)))).all()
    for job in jobs:
        job.status = "processing"
        job.attempts += 1
        job.locked_until = now + timedelta(seconds=LEASE_SECONDS)
    if jobs:
        db.commit()
    return jobs


def _record_failure(db: OrmSession, job: Job, config: SourceSyncConfig | None, source: Source | None, code: str, now: datetime) -> None:
    if config is not None:
        config.last_checked_at = now
        config.last_error_code = code
    job.last_error_code = code
    job.locked_until = None
    job.status = "failed" if job.attempts >= MAX_ATTEMPTS else "queued"
    job.available_at = now + timedelta(seconds=min(3600, 30 * (2 ** job.attempts)))
    if source is not None:
        add_audit_event(db, action="sources.sync", result="failure", actor_user_id=source.user_id, target=source.id, metadata={"error_code": code})


def _sync_one(db: OrmSession, settings: Settings, job: Job, now: datetime) -> None:
    source = db.get(Source, job.payload_json or "")
    config = db.scalar(select(SourceSyncConfig).where(SourceSyncConfig.source_id == (source.id if source else "")))
    if source is None or config is None or source.deleted_at is not None or source.status == "archived":
        job.status = "completed"
        job.completed_at = now
        job.locked_until = None
        return
    try:
        resolved = _resolve_sync_file(settings, config)
        if resolved is None:
            raise ValueError("approved_file_not_found")
        path, info = resolved
        content = _read_approved_file(path, info)
        observed_sha = str(info["sha256"])
        config.file_id = str(info["file_id"])
        config.last_checked_at = now
        config.last_observed_size = int(info["size_bytes"])
        config.last_observed_mtime_ns = path.stat().st_mtime_ns
        config.last_observed_sha256 = observed_sha
        if observed_sha == source.sha256:
            config.last_success_at = now
            config.last_error_code = None
            job.status = "completed"
            job.completed_at = now
            job.locked_until = None
            add_audit_event(db, action="sources.sync", result="no_change", actor_user_id=source.user_id, target=source.id)
            return
        destination = _source_root(settings) / source.stored_path
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        temporary.write_bytes(content)
        os.replace(temporary, destination)
        source.sha256 = observed_sha
        source.size_bytes = len(content)
        source.mime_type = str(info["mime_type"])
        source.status = "processing"
        source.last_error_code = None
        config.last_changed_at = now
        config.last_success_at = now
        config.last_error_code = None
        if _job_for_source(db, source.id) is None:
            db.add(Job(job_type="source_ingest", status="queued", payload_json=source.id, available_at=now - timedelta(seconds=1), idempotency_key=f"source:{source.id}:sync:{observed_sha}"))
        job.status = "completed"
        job.completed_at = now
        job.locked_until = None
        add_audit_event(db, action="sources.sync", result="changed", actor_user_id=source.user_id, target=source.id, metadata={"size_bytes": len(content)})
    except (OSError, ValueError, RuntimeError):
        _record_failure(db, job, config, source, "source_sync_failed", now)


def process_source_sync(db: OrmSession, settings: Settings, *, batch_size: int = 2) -> int:
    """Claim and process bounded synchronization jobs with retry leases."""
    now = datetime.now(UTC)
    enqueue_due_source_sync_jobs(db, now=now, batch_size=batch_size)
    jobs = _claim_jobs(db, now=datetime.now(UTC), batch_size=batch_size)
    for job in jobs:
        _sync_one(db, settings, job, now)
        db.commit()
    return len(jobs)
