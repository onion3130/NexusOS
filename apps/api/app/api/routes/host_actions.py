"""Authenticated safe host-action and maintenance routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as OrmSession

from app.core.config import Settings, get_settings
from app.db.models import AuditEvent, BackupRecord, HostActionProposal, Job
from app.db.session import get_db
from app.modules.host_actions.catalog import catalog, get_action
from app.modules.host_actions.schemas import ActionCatalogItem, ActionProposalCreate, ActionProposalResponse, AuditEventResponse, AuditListResponse, BackupResponse, JobResponse
from app.modules.host_actions.service import confirm_proposal, create_proposal, get_proposal, list_audit_events, list_backups, reject_proposal
from app.modules.identity.dependencies import AuthContext, get_auth_context, require_csrf, require_permission

router = APIRouter(prefix="/api/v1/system", tags=["host-actions"])


def _proposal(item: HostActionProposal) -> ActionProposalResponse:
    action = get_action(item.action_key)
    if action is None:
        raise HTTPException(status_code=500, detail="action_catalog_error")
    return ActionProposalResponse(id=item.id, action_key=item.action_key, title=action.title, description=action.description, risk_level=item.risk_level, status=item.status, input=json.loads(item.input_json), expires_at=item.expires_at, created_at=item.created_at, confirmed_at=item.confirmed_at, completed_at=item.completed_at, job_id=item.job_id, error_code=item.error_code)


def _backup(item: BackupRecord) -> BackupResponse:
    return BackupResponse(id=item.id, relative_path=item.relative_path, size_bytes=item.size_bytes, sha256=item.sha256, status=item.status, integrity_result=item.integrity_result, created_at=item.created_at, verified_at=item.verified_at)


def _job(item: Job) -> JobResponse:
    return JobResponse(id=item.id, job_type=item.job_type, status=item.status, attempts=item.attempts, available_at=item.available_at, started_at=item.started_at, completed_at=item.completed_at, last_error_code=item.last_error_code)


def _audit(item: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(id=item.id, action=item.action, target=item.target, result=item.result, metadata=json.loads(item.metadata_json or "{}"), created_at=item.created_at)


@router.get("/actions", response_model=list[ActionCatalogItem])
def actions(context: AuthContext = Depends(get_auth_context)) -> list[ActionCatalogItem]:
    require_permission("system.host_actions", context)
    return catalog()


@router.post("/actions/proposals", response_model=ActionProposalResponse, status_code=status.HTTP_201_CREATED)
def propose(payload: ActionProposalCreate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> ActionProposalResponse:
    require_csrf(request, context)
    require_permission("system.host_actions", context)
    try:
        item = create_proposal(db, context.user.id, payload, request.headers.get("Idempotency-Key"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _proposal(item)


@router.get("/actions/proposals", response_model=list[ActionProposalResponse])
def proposals(db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> list[ActionProposalResponse]:
    require_permission("system.host_actions", context)
    from sqlalchemy import select
    items = db.scalars(select(HostActionProposal).where(HostActionProposal.user_id == context.user.id).order_by(HostActionProposal.created_at.desc()).limit(50)).all()
    return [_proposal(item) for item in items]


@router.get("/actions/proposals/{proposal_id}", response_model=ActionProposalResponse)
def proposal(proposal_id: str, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> ActionProposalResponse:
    require_permission("system.host_actions", context)
    item = get_proposal(db, context.user.id, proposal_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Action proposal not found")
    return _proposal(item)


@router.post("/actions/proposals/{proposal_id}/confirm", response_model=ActionProposalResponse)
def confirm(proposal_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> ActionProposalResponse:
    require_csrf(request, context)
    require_permission("system.host_actions", context)
    item = confirm_proposal(db, context.user.id, proposal_id, request.headers.get("Idempotency-Key"))
    if item is None:
        raise HTTPException(status_code=404, detail="Action proposal not found")
    return _proposal(item)


@router.post("/actions/proposals/{proposal_id}/reject", response_model=ActionProposalResponse)
def reject(proposal_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> ActionProposalResponse:
    require_csrf(request, context)
    require_permission("system.host_actions", context)
    item = reject_proposal(db, context.user.id, proposal_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Action proposal not found")
    return _proposal(item)


@router.get("/backups", response_model=list[BackupResponse])
def backups(db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> list[BackupResponse]:
    require_permission("system.backups.read", context)
    return [_backup(item) for item in list_backups(db, context.user.id)]


@router.get("/jobs/{job_id}", response_model=JobResponse)
def job(job_id: str, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> JobResponse:
    require_permission("system.host_actions", context)
    from sqlalchemy import select
    item = db.scalar(select(Job).join(HostActionProposal, HostActionProposal.job_id == Job.id).where(Job.id == job_id, HostActionProposal.user_id == context.user.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job(item)


@router.get("/audit", response_model=AuditListResponse)
def audit(db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> AuditListResponse:
    require_permission("system.audit.read", context)
    items = list_audit_events(db, context.user.id)
    return AuditListResponse(items=[_audit(item) for item in items])
