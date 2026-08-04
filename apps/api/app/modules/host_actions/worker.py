"""Dedicated bounded worker processing for confirmed host actions."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session as OrmSession

from app.db.base import utc_now
from app.db.models import HostActionProposal, Job
from app.modules.host_actions.executor import execute_action
from app.modules.identity.service import add_audit_event

MAX_ATTEMPTS = 3
LEASE = timedelta(minutes=5)


def _current_time(now: datetime | None) -> datetime:
    """Normalize an optional test clock to aware UTC."""
    value = now or utc_now()
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _fail_expired_jobs(db: OrmSession, current: datetime) -> None:
    """Move exhausted stale jobs to a terminal state after a worker crash."""
    jobs = db.scalars(
        select(Job).where(
            Job.job_type == "host_action",
            Job.status == "processing",
            Job.locked_until <= current,
            Job.attempts >= MAX_ATTEMPTS,
        )
    ).all()
    for job in jobs:
        proposal_id = _proposal_id(job)
        proposal = db.get(HostActionProposal, proposal_id) if proposal_id else None
        if proposal is not None and proposal.status in {"queued", "processing"}:
            proposal.status = "failed"
            proposal.error_code = "worker_retry_limit"
            proposal.completed_at = current
            add_audit_event(
                db,
                action="host_action.execute",
                result="failure",
                actor_user_id=proposal.user_id,
                target=proposal.id,
                metadata={"action": proposal.action_key, "job_id": job.id, "error": "worker_retry_limit"},
            )
        job.status = "failed"
        job.locked_until = None
        job.last_error_code = "worker_retry_limit"
        job.completed_at = current
    if jobs:
        db.commit()


def _proposal_id(job: Job) -> str | None:
    """Extract a bounded proposal identifier from a durable job payload."""
    try:
        value = json.loads(job.payload_json or "{}").get("proposal_id")
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, str) and value else None


def process_host_actions(
    db: OrmSession,
    *,
    data_dir,
    database_url: str,
    replication_destination=None,
    encryption_key: str | None = None,
    now: datetime | None = None,
    batch_size: int = 10,
) -> int:
    """Claim and execute a small batch of confirmed actions with crash recovery."""
    current = _current_time(now)
    _fail_expired_jobs(db, current)
    processed = 0
    for _ in range(max(1, min(batch_size, 20))):
        candidate = db.scalar(
            select(Job.id)
            .where(
                Job.job_type == "host_action",
                Job.attempts < MAX_ATTEMPTS,
                Job.available_at <= current,
                or_(
                    Job.status == "queued",
                    (Job.status == "processing") & (Job.locked_until <= current),
                ),
            )
            .order_by(Job.created_at)
            .limit(1)
        )
        if candidate is None:
            break
        claim = db.execute(
            update(Job)
            .where(
                Job.id == candidate,
                Job.attempts < MAX_ATTEMPTS,
                or_(
                    Job.status == "queued",
                    (Job.status == "processing") & (Job.locked_until <= current),
                ),
            )
            .values(
                status="processing",
                attempts=Job.attempts + 1,
                locked_until=current + LEASE,
                started_at=current,
            )
        )
        db.commit()
        if claim.rowcount != 1:
            continue
        job = db.get(Job, candidate)
        if job is None:
            continue
        proposal_id = _proposal_id(job)
        proposal = db.get(HostActionProposal, proposal_id) if proposal_id else None
        if proposal is None or proposal.status not in {"queued", "processing"}:
            job.status = "failed"
            job.last_error_code = "proposal_unavailable"
            job.locked_until = None
            job.completed_at = current
            db.commit()
            processed += 1
            continue
        if proposal.status == "succeeded":
            job.status = "completed"
            job.locked_until = None
            job.completed_at = current
            db.commit()
            processed += 1
            continue
        proposal.status = "processing"
        db.commit()
        try:
            result = execute_action(
                proposal.action_key,
                json.loads(proposal.input_json),
                data_dir=data_dir,
                database_url=database_url,
                user_id=proposal.user_id,
                db=db,
                operation_id=job.id,
                replication_destination=replication_destination,
                encryption_key=encryption_key,
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            result = None
            error_code = str(exc) if isinstance(exc, ValueError) and str(exc) else "host_action_failed"
        except Exception:
            result = None
            error_code = "host_action_failed"
        if result is not None:
            if result.get("restart_required"):
                # The live database was atomically replaced by the restore
                # adapter. The proposal/job rows now belong to the superseded
                # pre-restore database, and the adapter wrote its own restore
                # audit row inside the restored database before the swap, so
                # no ORM completion writes are attempted against the replaced
                # file (they would target rows that no longer exist).
                db.commit()
            else:
                proposal.status = "succeeded"
                proposal.completed_at = current
                proposal.error_code = None
                job.status = "completed"
                job.payload_json = json.dumps(
                    {"proposal_id": proposal.id, "result": result}, separators=(",", ":")
                )[:16000]
                job.locked_until = None
                job.completed_at = current
                add_audit_event(
                    db,
                    action="host_action.execute",
                    result="success",
                    actor_user_id=proposal.user_id,
                    target=proposal.id,
                    metadata={"action": proposal.action_key, "job_id": job.id},
                )
        elif job.attempts < MAX_ATTEMPTS:
            proposal.status = "queued"
            proposal.error_code = error_code
            job.status = "queued"
            job.available_at = current + timedelta(seconds=30 * job.attempts)
            job.locked_until = None
            job.last_error_code = error_code
            add_audit_event(
                db,
                action="host_action.execute",
                result="retry",
                actor_user_id=proposal.user_id,
                target=proposal.id,
                metadata={"action": proposal.action_key, "job_id": job.id, "attempt": job.attempts},
            )
        else:
            proposal.status = "failed"
            proposal.error_code = error_code
            proposal.completed_at = current
            job.status = "failed"
            job.last_error_code = error_code
            job.locked_until = None
            job.completed_at = current
            add_audit_event(
                db,
                action="host_action.execute",
                result="failure",
                actor_user_id=proposal.user_id,
                target=proposal.id,
                metadata={"action": proposal.action_key, "job_id": job.id, "attempt": job.attempts},
            )
        db.commit()
        processed += 1
    return processed
