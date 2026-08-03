"""Workspace view orchestration and server-side source boundaries."""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.modules.workspace_views.adapters.docker import list_containers
from app.modules.workspace_views.adapters.files import scan_recent_files
from app.modules.workspace_views.adapters.git import discover_repositories
from app.modules.workspace_views.adapters.projects import discover_projects
from app.modules.workspace_views.schemas import DockerContainerListResponse, FileListResponse, GitRepositoryListResponse, ProjectListResponse


def configured_roots(settings: Settings) -> list[tuple[str, Path]]:
    """Resolve only server-configured workspace roots, never request paths."""
    raw = settings.workspace_roots.strip()
    if not raw:
        return [("data", settings.data_dir)]
    result: list[tuple[str, Path]] = []
    data_root = settings.data_dir.expanduser().resolve()
    for index, value in enumerate(raw.split(",")[:8]):
        path = Path(value.strip()).expanduser()
        if not path.is_absolute():
            path = (data_root / path).resolve()
            if path != data_root and data_root not in path.parents:
                continue
        result.append((f"root-{index + 1}", path))
    return result or [("data", data_root)]


def recent_files(settings: Settings, limit: int = 100) -> FileListResponse:
    """Return bounded metadata from approved roots."""
    return FileListResponse(items=scan_recent_files(configured_roots(settings), limit=limit))


def projects(settings: Settings) -> ProjectListResponse:
    """Return direct-child projects from approved roots."""
    return ProjectListResponse(items=discover_projects(configured_roots(settings)))


def repositories(settings: Settings) -> GitRepositoryListResponse:
    """Return safe Git metadata from approved roots."""
    return GitRepositoryListResponse(items=discover_repositories(configured_roots(settings)))


class WorkspaceViewService:
    """Server-configured facade shared by routes and assistant tools."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def recent_files(self, limit: int = 50) -> FileListResponse:
        return recent_files(self.settings, limit)

    def projects(self) -> ProjectListResponse:
        return projects(self.settings)

    def repositories(self) -> GitRepositoryListResponse:
        return repositories(self.settings)

    def containers(self) -> DockerContainerListResponse:
        return containers(self.settings)


def containers(settings: Settings) -> DockerContainerListResponse:
    """Return sanitized Docker metadata only when an operator-mounted socket exists."""
    socket_path = Path(settings.docker_socket_path) if settings.docker_socket_path.strip() else None
    if socket_path is None or not socket_path.is_socket():
        return DockerContainerListResponse(items=[], available=False, reason="docker_unavailable")
    try:
        return DockerContainerListResponse(items=list_containers(socket_path), available=True)
    except (OSError, TimeoutError, ValueError, UnicodeError):
        return DockerContainerListResponse(items=[], available=False, reason="docker_unavailable")
