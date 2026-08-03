"""Project metadata discovery over fixed approved roots."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.modules.workspace_views.schemas import ProjectView

_MARKERS = {
    "package.json": "Node.js",
    "pyproject.toml": "Python",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "docker-compose.yml": "Docker Compose",
}


def discover_projects(roots: list[tuple[str, Path]]) -> list[ProjectView]:
    """Discover only direct child directories with known project markers."""
    result: list[ProjectView] = []
    for source, configured_root in roots:
        root = configured_root.expanduser().resolve()
        if not root.is_dir():
            continue
        try:
            children = sorted(root.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            continue
        for child in children[:100]:
            if not child.is_dir() or child.is_symlink() or child.name.startswith("."):
                continue
            project_type = next((kind for marker, kind in _MARKERS.items() if (child / marker).is_file()), None)
            git_root = child / ".git"
            if project_type is None and not git_root.is_dir():
                continue
            try:
                modified = datetime.fromtimestamp(child.stat().st_mtime, UTC)
            except OSError:
                modified = None
            project_id = f"{source}:{child.name}"
            result.append(ProjectView(id=project_id[:128], name=child.name[:160], path=child.name, project_type=project_type or "Git repository", modified_at=modified, repository_id=project_id if git_root.is_dir() else None))
    return result[:100]
