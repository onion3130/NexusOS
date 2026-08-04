"""Media indexing service over operator-approved media roots."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.core.config import Settings
from app.db.base import utc_now
from app.db.models import Job, MediaItem
from app.modules.identity.service import add_audit_event

THUMBNAIL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".avif"}
INDEXABLE_EXTENSIONS = THUMBNAIL_EXTENSIONS | {".mp4", ".mov", ".mkv", ".webm", ".mp3", ".flac", ".wav", ".ogg", ".m4a", ".pdf", ".txt", ".md"}
_SENSITIVE_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519", "authorized_keys"}
MAX_DEPTH = 6
MAX_ITEMS = 5000
RESCAN_JOB_KEY = "media-rescan"


def _safe_name(path: Path) -> bool:
    """Exclude credential files and dot-directory noise from the index."""
    return path.name not in _SENSITIVE_NAMES and not path.name.endswith((".pem", ".key")) and not path.name.startswith(".")


def configured_media_roots(settings: Settings) -> list[tuple[str, Path]]:
    """Resolve only server-configured media roots, never request paths."""
    raw = settings.media_roots.strip()
    if not raw:
        return []
    result: list[tuple[str, Path]] = []
    data_root = settings.data_dir.expanduser().resolve()
    for index, value in enumerate(raw.split(",")[:8]):
        path = Path(value.strip()).expanduser()
        if not path.is_absolute():
            path = (data_root / path).resolve()
            if path != data_root and data_root not in path.parents:
                continue
        result.append((f"root-{index + 1}", path))
    return result


def _relative(root: Path, path: Path) -> str:
    """Return a normalized user-safe relative path."""
    return path.relative_to(root).as_posix()


def _hash_file(path: Path) -> str:
    """Hash a file in bounded reads."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mime_type(path: Path) -> str:
    """Return a stable MIME type, defaulting by extension."""
    guess, _ = mimetypes.guess_type(path.name)
    return guess or "application/octet-stream"


def _thumbnails_dir(data_dir: Path) -> Path:
    """Return the derived thumbnail directory beneath the data volume."""
    directory = data_dir.expanduser().resolve() / "media-thumbnails"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _generate_thumbnail(source: Path, thumbnails_dir: Path, max_dimension: int) -> str | None:
    """Create a bounded JPEG thumbnail next to the index; never modify the original."""
    try:
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = 60_000_000  # bound decompression bombs
        with Image.open(source) as image:
            image = image.convert("RGB")
            image.thumbnail((max_dimension, max_dimension))
            digest = _hash_file(source)
            target = thumbnails_dir / f"{digest}.jpg"
            if not target.exists():
                temporary = target.with_suffix(".tmp")
                image.save(temporary, "JPEG", quality=82, optimize=True)
                temporary.replace(target)
            return target.name
    except (OSError, ValueError, Exception):  # noqa: BLE001 - corrupt media is skipped
        return None


def _scan_files(roots: list[tuple[str, Path]], max_size_bytes: int, max_dimension: int, thumbnails_dir: Path) -> tuple[list[dict[str, object]], int]:
    """Walk approved roots once and return normalized index rows plus thumbnails created."""
    rows: list[dict[str, object]] = []
    thumbnails_created = 0
    for source, configured_root in roots:
        root = configured_root.expanduser().resolve()
        if not root.is_dir():
            continue
        for current, directories, files in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            depth = len(current_path.relative_to(root).parts)
            directories[:] = [name for name in directories if _safe_name(current_path / name) and not (current_path / name).is_symlink() and depth < MAX_DEPTH]
            for filename in files:
                path = current_path / filename
                if not _safe_name(path) or path.is_symlink():
                    continue
                extension = path.suffix.lower()
                if extension not in INDEXABLE_EXTENSIONS:
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if stat.st_size <= 0 or stat.st_size > max_size_bytes:
                    continue
                try:
                    sha256 = _hash_file(path)
                except OSError:
                    continue
                thumbnail_path = None
                width = height = None
                if extension in THUMBNAIL_EXTENSIONS:
                    try:
                        from PIL import Image

                        Image.MAX_IMAGE_PIXELS = 60_000_000
                        with Image.open(path) as image:
                            width, height = image.size
                    except (OSError, ValueError):
                        width = height = None
                    thumbnail_path = _generate_thumbnail(path, thumbnails_dir, max_dimension)
                    if thumbnail_path is not None:
                        thumbnails_created += 1
                relative = _relative(root, path)
                rows.append(
                    {
                        "root_key": source,
                        "relative_path": relative,
                        "file_name": path.name,
                        "extension": extension.lstrip("."),
                        "mime_type": _mime_type(path),
                        "size_bytes": stat.st_size,
                        "sha256": sha256,
                        "width": width,
                        "height": height,
                        "thumbnail_path": thumbnail_path,
                        "indexed_at": utc_now(),
                    }
                )
    return rows, thumbnails_created


def scan_media_library(db: OrmSession, *, data_dir: Path, media_roots: list[tuple[str, Path]], max_size_bytes: int = 200 * 1024 * 1024, max_dimension: int = 320) -> dict[str, int]:
    """Upsert the derived media index from approved roots; soft-delete vanished files."""
    thumbnails_dir = _thumbnails_dir(data_dir)
    rows, thumbnails_created = _scan_files(media_roots, max_size_bytes, max_dimension, thumbnails_dir)
    if not media_roots:
        return {"indexed": 0, "updated": 0, "removed": 0, "thumbnails": 0}
    seen: set[tuple[str, str]] = set()
    indexed = updated = 0
    now = utc_now()
    for row in rows:
        key = (str(row["root_key"]), str(row["relative_path"]))
        seen.add(key)
        existing = db.scalar(select(MediaItem).where(MediaItem.root_key == key[0], MediaItem.relative_path == key[1]))
        if existing is None:
            db.add(MediaItem(user_id=None, **row))  # type: ignore[arg-type]
            indexed += 1
        else:
            changed = any(getattr(existing, field) != row[field] for field in ("sha256", "size_bytes", "width", "height", "thumbnail_path"))
            if changed:
                for field, value in row.items():
                    setattr(existing, field, value)
                existing.deleted_at = None
                existing.updated_at = now
                updated += 1
    removed = 0
    if seen:
        root_keys = {key[0] for key in seen}
        active_keys = set(seen)
        for item in db.scalars(select(MediaItem).where(MediaItem.root_key.in_(root_keys))).all():
            if (item.root_key, item.relative_path) not in active_keys and item.deleted_at is None:
                item.deleted_at = now
                removed += 1
    if rows:
        db.commit()
    return {"indexed": indexed, "updated": updated, "removed": removed, "thumbnails": thumbnails_created}


def queue_media_rescan(db: OrmSession) -> tuple[bool, str | None]:
    """Queue exactly one rescan job idempotently; refuse while one is pending."""
    existing = db.scalar(
        select(Job).where(Job.job_type == "media_rescan", Job.idempotency_key == RESCAN_JOB_KEY, Job.status.in_(("queued", "processing")))
    )
    if existing is not None:
        return False, existing.id
    job = Job(job_type="media_rescan", status="queued", available_at=utc_now(), idempotency_key=RESCAN_JOB_KEY)
    db.add(job)
    db.commit()
    return True, job.id


def process_media_rescans(db: OrmSession, *, data_dir: Path, media_roots: list[tuple[str, Path]], max_size_bytes: int, max_dimension: int) -> int:
    """Run pending rescan jobs in a bounded batch; requires configured roots."""
    if not media_roots:
        return 0
    processed = 0
    jobs = db.scalars(
        select(Job).where(Job.job_type == "media_rescan", Job.status.in_(("queued", "processing")), Job.attempts < 3).order_by(Job.created_at).limit(1)
    ).all()
    for job in jobs:
        job.status = "processing"
        job.attempts += 1
        job.started_at = utc_now()
        db.commit()
        try:
            summary = scan_media_library(db, data_dir=data_dir, media_roots=media_roots, max_size_bytes=max_size_bytes, max_dimension=max_dimension)
            job.status = "completed"
            job.completed_at = utc_now()
            add_audit_event(db, action="media.rescan", result="success", target=job.id, metadata=summary)
        except Exception:
            job.status = "queued"
            job.last_error_code = "scan_failed"
        db.commit()
        processed += 1
    return processed


def list_media_items(db: OrmSession, *, extension: str | None = None, mime_type: str | None = None, folder: str | None = None, limit: int = 100, cursor: str | None = None) -> list[MediaItem]:
    """List current index rows with bounded filters and cursor pagination."""
    statement = select(MediaItem).where(MediaItem.deleted_at.is_(None))
    if extension:
        statement = statement.where(MediaItem.extension == extension.lstrip(".").lower())
    if mime_type:
        statement = statement.where(MediaItem.mime_type == mime_type)
    if folder:
        statement = statement.where(MediaItem.relative_path.like(f"{folder.rstrip('/')}/%"))
    if cursor:
        statement = statement.where(MediaItem.id < cursor)
    return list(db.scalars(statement.order_by(MediaItem.updated_at, MediaItem.id).limit(max(1, min(limit, 200)))))


def resolve_media_path(db: OrmSession, item_id: str, roots: list[tuple[str, Path]]) -> tuple[Path, MediaItem] | None:
    """Resolve an indexed item's absolute path only when confined to an approved root."""
    item = db.get(MediaItem, item_id)
    if item is None or item.deleted_at is not None:
        return None
    for root_key, configured_root in roots:
        if root_key != item.root_key:
            continue
        root = configured_root.expanduser().resolve()
        candidate = (root / item.relative_path).resolve()
        if candidate == root or root in candidate.parents:
            if candidate.is_file():
                return candidate, item
    return None


def resolve_thumbnail_path(data_dir: Path, item: MediaItem) -> Path | None:
    """Resolve a derived thumbnail only beneath the data volume."""
    if not item.thumbnail_path:
        return None
    thumbnails_dir = _thumbnails_dir(data_dir)
    candidate = (thumbnails_dir / item.thumbnail_path).resolve()
    if thumbnails_dir in candidate.parents and candidate.is_file():
        return candidate
    return None
