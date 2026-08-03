"""Typed, bounded schemas for Milestone 9 workspace views."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FileEntry(BaseModel):
    """A safe file metadata entry with no host path disclosure."""

    path: str = Field(max_length=512)
    name: str = Field(max_length=255)
    size_bytes: int = Field(ge=0)
    modified_at: datetime
    source: str = Field(max_length=64)


class FileListResponse(BaseModel):
    """Bounded recent-file response."""

    items: list[FileEntry]
    next_cursor: str | None = None
    available: bool = True
    reason: str | None = None


class ProjectView(BaseModel):
    """Safe metadata for one configured project root."""

    id: str = Field(max_length=128)
    name: str = Field(max_length=160)
    path: str = Field(max_length=512)
    project_type: str = Field(max_length=64)
    modified_at: datetime | None
    repository_id: str | None = None


class ProjectListResponse(BaseModel):
    """Bounded project metadata response."""

    items: list[ProjectView]
    available: bool = True
    reason: str | None = None


class GitRepositoryView(BaseModel):
    """Sanitized read-only Git repository metadata."""

    id: str = Field(max_length=128)
    name: str = Field(max_length=160)
    path: str = Field(max_length=512)
    branch: str | None = Field(default=None, max_length=160)
    commit: str | None = Field(default=None, max_length=40)
    subject: str | None = Field(default=None, max_length=240)
    modified_at: datetime | None
    clean: bool | None
    ahead: int | None = Field(default=None, ge=0)
    behind: int | None = Field(default=None, ge=0)
    available: bool = True
    reason: str | None = None


class GitRepositoryListResponse(BaseModel):
    """Bounded Git repository response."""

    items: list[GitRepositoryView]
    available: bool = True
    reason: str | None = None


ContainerState = Literal["running", "exited", "created", "paused", "restarting", "removing", "dead", "unknown"]


class DockerContainerView(BaseModel):
    """Allowlisted Docker metadata without environment or mount contents."""

    id: str = Field(max_length=20)
    name: str = Field(max_length=160)
    image: str = Field(max_length=240)
    state: ContainerState
    health: str | None = Field(default=None, max_length=32)
    created_at: datetime | None
    ports: list[str] = Field(default_factory=list, max_length=32)
    restart_policy: str | None = Field(default=None, max_length=32)
    compose_service: str | None = Field(default=None, max_length=128)


class DockerContainerListResponse(BaseModel):
    """Bounded Docker metadata response."""

    items: list[DockerContainerView]
    available: bool = True
    reason: str | None = None
