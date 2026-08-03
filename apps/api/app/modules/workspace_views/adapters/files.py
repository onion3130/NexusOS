"""Bounded filesystem metadata adapter with approved-root containment."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.modules.workspace_views.schemas import FileEntry

MAX_ITEMS = 100
MAX_DEPTH = 3
_SENSITIVE_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519", "authorized_keys"}


def _safe_name(path: Path) -> bool:
    """Exclude common credential files from the read-only view."""
    return path.name not in _SENSITIVE_NAMES and not path.name.endswith((".pem", ".key"))


def _relative(root: Path, path: Path) -> str:
    """Return a normalized user-safe relative path."""
    return path.relative_to(root).as_posix()


def scan_recent_files(roots: list[tuple[str, Path]], *, limit: int = MAX_ITEMS) -> list[FileEntry]:
    """Scan only configured roots, never following symlinks outside them."""
    entries: list[tuple[float, FileEntry]] = []
    bounded_limit = max(1, min(limit, MAX_ITEMS))
    for source, configured_root in roots:
        root = configured_root.expanduser().resolve()
        if not root.is_dir():
            continue
        for current, directories, files in __import__("os").walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            depth = len(current_path.relative_to(root).parts)
            directories[:] = [name for name in directories if _safe_name(current_path / name) and not (current_path / name).is_symlink() and depth < MAX_DEPTH]
            for filename in files:
                path = current_path / filename
                if not _safe_name(path) or path.is_symlink():
                    continue
                try:
                    stat = path.stat()
                    relative = _relative(root, path)
                except OSError:
                    continue
                entry = FileEntry(path=relative, name=path.name, size_bytes=stat.st_size, modified_at=datetime.fromtimestamp(stat.st_mtime, UTC), source=source)
                entries.append((stat.st_mtime, entry))
    entries.sort(key=lambda item: (item[0], item[1].path), reverse=True)
    return [entry for _, entry in entries[:bounded_limit]]
