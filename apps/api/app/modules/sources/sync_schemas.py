"""Schemas for approved-root source synchronization."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

MIN_INTERVAL_SECONDS = 900
MAX_INTERVAL_SECONDS = 86400


class SourceSyncUpdate(BaseModel):
    """Enable or update a synchronization policy."""

    model_config = {"extra": "forbid"}

    enabled: bool = True
    interval_seconds: int = Field(default=3600, ge=MIN_INTERVAL_SECONDS, le=MAX_INTERVAL_SECONDS)


class SourceSyncResponse(BaseModel):
    """Redacted synchronization status."""

    id: str
    enabled: bool
    interval_seconds: int
    last_checked_at: datetime | None
    last_changed_at: datetime | None
    last_success_at: datetime | None
    last_error_code: str | None
    next_check_at: datetime | None


class SourceSyncJobResponse(BaseModel):
    """Bounded status for a queued synchronization check."""

    id: str
    source_id: str
    status: str
    attempts: int
    error_code: str | None
    created_at: datetime
    completed_at: datetime | None
