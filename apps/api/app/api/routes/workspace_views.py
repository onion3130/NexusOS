"""Authenticated read-only workspace view routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.config import Settings, get_settings
from app.modules.identity.dependencies import AuthContext, get_auth_context, require_permission
from app.modules.workspace_views.schemas import DockerContainerListResponse, FileListResponse, GitRepositoryListResponse, ProjectListResponse
from app.modules.workspace_views.service import WorkspaceViewService

router = APIRouter(prefix="/api/v1", tags=["workspace-views"])


def _authorize(context: AuthContext) -> None:
    """Require the dedicated server-side read permission."""
    require_permission("workspace_views.read", context)


@router.get("/files/recent", response_model=FileListResponse)
def files_recent(limit: int = Query(default=50, ge=1, le=100), context: AuthContext = Depends(get_auth_context), settings: Settings = Depends(get_settings)) -> FileListResponse:
    """Return bounded recent file metadata beneath approved roots."""
    _authorize(context)
    return WorkspaceViewService(settings).recent_files(limit)


@router.get("/projects", response_model=ProjectListResponse)
def project_list(context: AuthContext = Depends(get_auth_context), settings: Settings = Depends(get_settings)) -> ProjectListResponse:
    """Return safe project metadata beneath approved roots."""
    _authorize(context)
    return WorkspaceViewService(settings).projects()


@router.get("/git/repositories", response_model=GitRepositoryListResponse)
def git_repositories(context: AuthContext = Depends(get_auth_context), settings: Settings = Depends(get_settings)) -> GitRepositoryListResponse:
    """Return bounded, read-only Git status beneath approved roots."""
    _authorize(context)
    return WorkspaceViewService(settings).repositories()


@router.get("/docker/containers", response_model=DockerContainerListResponse)
def docker_containers(context: AuthContext = Depends(get_auth_context), settings: Settings = Depends(get_settings)) -> DockerContainerListResponse:
    """Return sanitized Docker metadata when the optional socket boundary is available."""
    _authorize(context)
    return WorkspaceViewService(settings).containers()
