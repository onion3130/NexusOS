"""Public schemas for safe host actions and maintenance metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ActionKey = Literal["maintenance.create_backup", "maintenance.verify_backup", "maintenance.integrity_check", "maintenance.restore_backup", "maintenance.retention_cleanup", "maintenance.rotate_encryption_key"]
ProposalStatus = Literal["proposed", "confirmed", "queued", "processing", "succeeded", "failed", "rejected", "expired"]
RiskLevel = Literal["low", "medium", "high"]


class ActionCatalogItem(BaseModel):
    key: ActionKey
    title: str
    description: str
    risk_level: RiskLevel
    requires_confirmation: bool = True
    enabled: bool = True


class ActionProposalCreate(BaseModel):
    model_config = {"extra": "forbid"}
    action_key: ActionKey
    input: dict[str, object] = Field(default_factory=dict)


class ActionProposalResponse(BaseModel):
    id: str
    action_key: ActionKey
    title: str
    description: str
    risk_level: RiskLevel
    status: ProposalStatus
    input: dict[str, object]
    expires_at: datetime
    created_at: datetime
    confirmed_at: datetime | None
    completed_at: datetime | None
    job_id: str | None
    error_code: str | None


class ActionConfirmResponse(ActionProposalResponse):
    pass


class BackupResponse(BaseModel):
    id: str
    relative_path: str
    size_bytes: int
    sha256: str
    status: Literal["created", "verified", "failed", "deleted"]
    integrity_result: str | None
    created_at: datetime
    verified_at: datetime | None
    encryption_status: str | None = None
    encrypted_size_bytes: int | None = None
    replication_status: str | None = None
    replicated_at: datetime | None = None
    replication_error_code: str | None = None
    restored_at: datetime | None = None
    pruned_at: datetime | None = None


class RetentionPolicy(BaseModel):
    count: int
    days: int


class RetentionPreviewResponse(BaseModel):
    policy: RetentionPolicy
    to_prune: list[BackupResponse]
    retained: list[BackupResponse]


class JobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    attempts: int
    available_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    last_error_code: str | None


class AuditEventResponse(BaseModel):
    id: str
    action: str
    target: str | None
    result: str
    metadata: dict[str, object]
    created_at: datetime


class AuditListResponse(BaseModel):
    items: list[AuditEventResponse]
    next_cursor: str | None = None
