"""Read-only Git adapter with fixed commands and bounded subprocesses."""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from app.modules.workspace_views.schemas import GitRepositoryView

_TIMEOUT_SECONDS = 3
_OUTPUT_LIMIT = 4096


def _run_git(root: Path, *arguments: str) -> str | None:
    """Run one fixed Git command without shell evaluation or user arguments."""
    try:
        completed = subprocess.run(["git", "-C", str(root), *arguments], check=False, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS, env={"PATH": os.environ.get("PATH", "")})
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout[:_OUTPUT_LIMIT].strip()


def inspect_repository(repository_id: str, name: str, root: Path) -> GitRepositoryView:
    """Return sanitized repository state without exposing remotes or commands."""
    resolved = root.expanduser().resolve()
    branch = _run_git(resolved, "branch", "--show-current")
    commit = _run_git(resolved, "rev-parse", "--short=12", "HEAD")
    subject = _run_git(resolved, "log", "-1", "--format=%s")
    status = _run_git(resolved, "status", "--porcelain=v1")
    modified: datetime | None = None
    try:
        modified = datetime.fromtimestamp(resolved.stat().st_mtime, UTC)
    except OSError:
        pass
    available = branch is not None or commit is not None
    return GitRepositoryView(id=repository_id[:128], name=name[:160], path=name[:512], branch=branch or None, commit=commit or None, subject=subject or None, modified_at=modified, clean=(status == "" if status is not None else None), available=available, reason=None if available else "git_unavailable")


def discover_repositories(roots: list[tuple[str, Path]]) -> list[GitRepositoryView]:
    """Inspect only direct child Git repositories beneath approved roots."""
    result: list[GitRepositoryView] = []
    for source, configured_root in roots:
        root = configured_root.expanduser().resolve()
        if not root.is_dir():
            continue
        try:
            children = sorted(root.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            continue
        if (root / ".git").is_dir():
            result.append(inspect_repository(f"{source}:{root.name}", root.name, root))
        for child in children[:100]:
            if child.is_dir() and not child.is_symlink() and (child / ".git").is_dir():
                result.append(inspect_repository(f"{source}:{child.name}", child.name, child))
    return result[:100]
