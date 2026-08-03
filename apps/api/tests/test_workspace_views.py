"""Milestone 9 read-only workspace view tests."""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.modules.identity.service import bootstrap_owner
from app.modules.workspace_views.adapters.docker import list_containers
from app.modules.workspace_views.adapters.files import scan_recent_files
from app.modules.workspace_views.adapters.git import inspect_repository
from app.modules.workspace_views.adapters.projects import discover_projects
from app.modules.assistant.schemas import ProposedToolCall
from app.modules.assistant.tools.registry import ToolRegistry
from app.modules.system.service import SystemService
from app.modules.workspace_views.service import WorkspaceViewService, configured_roots


def _bootstrap_owner() -> None:
    """Create the fixture owner through the production bootstrap service."""
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()


def _login(client) -> None:
    """Authenticate the fixture owner."""
    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200


def test_file_and_project_adapters_filter_sensitive_entries(tmp_path: Path) -> None:
    """Approved-root metadata excludes credentials and discovers safe projects."""
    (tmp_path / "visible.txt").write_text("safe", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=never-return", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    files = scan_recent_files([("test", tmp_path)])
    assert any(item.name == "visible.txt" for item in files)
    assert all(item.name != ".env" for item in files)
    projects = discover_projects([("test", tmp_path)])
    assert projects[0].name == "project"
    assert projects[0].project_type == "Python"


def test_git_adapter_is_read_only_and_safe_for_non_repository(tmp_path: Path) -> None:
    """Git inspection returns a safe unavailable result without executing mutations."""
    result = inspect_repository("test:missing", "missing", tmp_path)
    assert result.available is False
    assert result.reason == "git_unavailable"
    assert result.commit is None


def test_docker_adapter_is_disabled_without_socket(tmp_path: Path) -> None:
    """Docker metadata remains unavailable unless the operator supplies a socket."""
    assert list_containers(tmp_path / "docker.sock") == []


def test_relative_workspace_roots_cannot_escape_data_dir(tmp_path: Path) -> None:
    """Relative operator configuration remains contained beneath DATA_DIR."""
    settings = type("SettingsStub", (), {"workspace_roots": "../outside,projects", "data_dir": tmp_path, "docker_socket_path": ""})()
    roots = configured_roots(settings)
    assert roots == [("root-2", tmp_path / "projects")]


def test_assistant_workspace_tools_are_read_only_and_permissioned(tmp_path: Path) -> None:
    """Workspace assistant tools share the service boundary and never require confirmation."""
    settings = type("SettingsStub", (), {"workspace_roots": "", "data_dir": tmp_path, "docker_socket_path": ""})()
    registry = ToolRegistry(SystemService(tmp_path), workspace_service=WorkspaceViewService(settings))
    permissions = {"workspace_views.read"}
    assert {item.key for item in registry.definitions(permissions)} == {"files.recent", "projects.list", "git.repositories", "docker.containers"}
    assert registry.requires_confirmation("files.recent") is False
    result = registry.execute(ProposedToolCall(provider_id="test", tool_key="docker.containers", arguments={}), permissions)
    assert result["available"] is False


def test_workspace_routes_require_authentication_and_are_read_only(client) -> None:
    """Every workspace view is protected and exposes only GET behavior."""
    paths = ["/api/v1/files/recent", "/api/v1/projects", "/api/v1/git/repositories", "/api/v1/docker/containers"]
    for path in paths:
        assert client.get(path).status_code == 401
    _bootstrap_owner()
    _login(client)
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, response.text
    docker = client.get("/api/v1/docker/containers").json()
    assert docker["available"] is False
    assert docker["reason"] == "docker_unavailable"
    assert client.post("/api/v1/projects").status_code == 405


def test_workspace_permission_is_migration_backed(configured_app, client) -> None:
    """The owner receives the dedicated workspace view permission from migration 0007."""
    _bootstrap_owner()
    _login(client)
    permissions = client.get("/api/v1/auth/me").json()["permissions"]
    assert "workspace_views.read" in permissions
    get_settings.cache_clear()
