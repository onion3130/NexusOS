"""Safe host-action proposal and lifecycle services."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.db.base import utc_now
from app.db.models import AuditEvent, BackupRecord, HostActionProposal, Job
from app.modules.host_actions.catalog import get_action, is_valid_input
from app.modules.host_actions.schemas import ActionProposalCreate
from app.modules.identity.service import add_audit_event

PROPOSAL_TTL = timedelta(minutes=10)


def _key(user_id: str, raw: str) -> str:
    return hashlib.sha256(f"host-action:{user_id}:{raw}".encode()).hexdigest()


def create_proposal(db: OrmSession, user_id: str, payload: ActionProposalCreate, idempotency_key: str | None) -> HostActionProposal:
    """Persist a proposed action; no host operation occurs at this stage."""
    action = get_action(payload.action_key)
    if action is None or not action.enabled or not is_valid_input(payload.action_key, payload.input):
        raise ValueError("action_not_allowed")
    scoped_key = _key(user_id, idempotency_key) if idempotency_key else None
    if scoped_key:
        existing = db.scalar(select(HostActionProposal).where(HostActionProposal.idempotency_key == scoped_key))
        if existing:
            if existing.input_json != json.dumps(payload.input, sort_keys=True, separators=(",", ":")) or existing.action_key != payload.action_key:
                raise ValueError("Idempotency-Key was already used for a different action")
            return existing
    proposal = HostActionProposal(user_id=user_id, action_key=payload.action_key, risk_level=action.risk_level, status="proposed", input_json=json.dumps(payload.input, sort_keys=True, separators=(",", ":")), idempotency_key=scoped_key, expires_at=utc_now() + PROPOSAL_TTL)
    db.add(proposal)
    db.flush()
    add_audit_event(db, action="host_action.propose", result="success", actor_user_id=user_id, target=proposal.id, metadata={"action": payload.action_key, "risk": action.risk_level})
    db.commit()
    return proposal


def confirm_proposal(db: OrmSession, user_id: str, proposal_id: str, idempotency_key: str | None, *, now: datetime | None = None) -> HostActionProposal | None:
    """Confirm a non-expired proposal and enqueue exactly one bounded worker job."""
    proposal = db.scalar(select(HostActionProposal).where(HostActionProposal.id == proposal_id, HostActionProposal.user_id == user_id))
    if proposal is None:
        return None
    current = now or datetime.now(UTC)
    if proposal.status == "queued" or proposal.status in {"processing", "succeeded"}:
        return proposal
    if proposal.status != "proposed" or proposal.expires_at.replace(tzinfo=UTC) <= current:
        if proposal.status == "proposed":
            proposal.status = "expired"
            add_audit_event(db, action="host_action.confirm", result="expired", actor_user_id=user_id, target=proposal.id)
            db.commit()
        return proposal
    job_key = _key(user_id, idempotency_key or proposal.id)
    existing_job = db.scalar(select(Job).where(Job.idempotency_key == job_key))
    if existing_job is None:
        job = Job(job_type="host_action", status="queued", payload_json=json.dumps({"proposal_id": proposal.id}, separators=(",", ":")), available_at=utc_now(), idempotency_key=job_key)
        db.add(job)
        db.flush()
        proposal.job_id = job.id
    proposal.status = "queued"
    proposal.confirmed_at = current
    add_audit_event(db, action="host_action.confirm", result="success", actor_user_id=user_id, target=proposal.id, metadata={"action": proposal.action_key})
    db.commit()
    return proposal


def reject_proposal(db: OrmSession, user_id: str, proposal_id: str) -> HostActionProposal | None:
    """Reject a proposed action without creating a job."""
    proposal = db.scalar(select(HostActionProposal).where(HostActionProposal.id == proposal_id, HostActionProposal.user_id == user_id))
    if proposal is None:
        return None
    if proposal.status == "proposed":
        proposal.status = "rejected"
        add_audit_event(db, action="host_action.reject", result="success", actor_user_id=user_id, target=proposal.id)
        db.commit()
    return proposal


def get_proposal(db: OrmSession, user_id: str, proposal_id: str) -> HostActionProposal | None:
    return db.scalar(select(HostActionProposal).where(HostActionProposal.id == proposal_id, HostActionProposal.user_id == user_id))


def list_backups(db: OrmSession, user_id: str) -> list[BackupRecord]:
    """Return the current user's non-pruned backup records, newest first."""
    return list(db.scalars(select(BackupRecord).where(BackupRecord.user_id == user_id, BackupRecord.status != "deleted").order_by(BackupRecord.created_at.desc()).limit(100)))


def list_audit_events(db: OrmSession, user_id: str) -> list[AuditEvent]:
    """Return only events performed by the current user, bounded for the UI."""
    return list(db.scalars(select(AuditEvent).where(AuditEvent.actor_user_id == user_id, AuditEvent.action.like("host_action.%")).order_by(AuditEvent.created_at.desc()).limit(100)))
