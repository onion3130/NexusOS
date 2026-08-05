"""Schemas for external source ingestion and lifecycle management."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.sources.sync_schemas import SourceSyncResponse

SourceKind = Literal["upload", "approved_file"]
SourceStatus = Literal["processing", "ready", "failed", "archived"]


class SourceResponse(BaseModel):
    id: str
    kind: SourceKind
    title: str
    original_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    status: SourceStatus
    current_version: int
    last_ingested_at: datetime | None
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    sync: SourceSyncResponse | None = None


class SourceListResponse(BaseModel):
    items: list[SourceResponse]
    next_cursor: str | None = None


class SourceVersionResponse(BaseModel):
    id: str
    version: int
    content_hash: str
    content_length: int
    parser: str
    parser_version: str
    created_at: datetime


class SourceVersionsResponse(BaseModel):
    items: list[SourceVersionResponse]


class SourceChunkResponse(BaseModel):
    id: str
    source_version_id: str
    chunk_index: int
    content: str
    content_hash: str
    start_offset: int
    end_offset: int
    source_version: int
    created_at: datetime


class SourceChunksResponse(BaseModel):
    items: list[SourceChunkResponse]


class ApprovedFileResponse(BaseModel):
    file_id: str
    root_key: str
    relative_path: str
    name: str
    mime_type: str
    size_bytes: int
    sha256: str


class ApprovedFileListResponse(BaseModel):
    items: list[ApprovedFileResponse]


class SourceJobResponse(BaseModel):
    id: str
    source_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    attempts: int
    error_code: str | None
    created_at: datetime
    completed_at: datetime | None


class SourceImportRequest(BaseModel):
    model_config = {"extra": "forbid"}

    file_id: str = Field(min_length=1, max_length=200)
    title: str | None = Field(default=None, max_length=160)

    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return value.strip() if value else None
