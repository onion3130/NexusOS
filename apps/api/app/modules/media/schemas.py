"""Public schemas for the derived media library index."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MediaItemResponse(BaseModel):
    id: str
    root_key: str
    relative_path: str
    file_name: str
    extension: str
    mime_type: str
    size_bytes: int
    sha256: str
    width: int | None
    height: int | None
    has_thumbnail: bool
    indexed_at: datetime
    updated_at: datetime


class MediaListResponse(BaseModel):
    items: list[MediaItemResponse]
    next_cursor: str | None = None


class MediaRescanResponse(BaseModel):
    queued: bool = True
    job_id: str | None = Field(default=None)
    roots_configured: bool
