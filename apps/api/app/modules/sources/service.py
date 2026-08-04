"""Safe external source storage, lifecycle, and ingestion services."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import shutil
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.core.config import Settings
from app.db.base import utc_now
from app.db.models import Job, Source, SourceChunk, SourceVersion
from app.modules.identity.service import add_audit_event
from app.modules.notes.service import _split_chunks
from app.modules.sources.schemas import SourceImportRequest

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SOURCE_COUNT = 500
MAX_CHUNKS = 500
ALLOWED_EXTENSIONS = {".txt": "text/plain", ".md": "text/markdown", ".markdown": "text/markdown", ".pdf": "application/pdf"}
SENSITIVE_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519", "authorized_keys"}
SOURCE_JOB_TYPE = "source_ingest"


def _safe_name(name: str) -> bool:
    """Reject credential-like or hidden names."""
    return bool(name) and name not in SENSITIVE_NAMES and not name.startswith(".") and not name.endswith((".pem", ".key", ".p12", ".pfx"))


def _source_root(settings: Settings) -> Path:
    """Return the server-owned upload root."""
    root = (settings.data_dir / "sources").expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _hash_file(path: Path) -> tuple[int, str]:
    """Hash one file using bounded reads."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            if size > MAX_UPLOAD_BYTES:
                raise ValueError("source exceeds maximum size")
            digest.update(block)
    return size, digest.hexdigest()


def _detect_text(path: Path, extension: str) -> str:
    """Read an allowlisted text source with strict UTF-8 decoding."""
    if extension == ".pdf":
        raise ValueError("pdf_ingestion_not_enabled")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("source_must_be_utf8_text") from exc


def _mime_for(name: str) -> str:
    extension = Path(name).suffix.lower()
    return ALLOWED_EXTENSIONS.get(extension, mimetypes.guess_type(name)[0] or "application/octet-stream")


def _extension(name: str) -> str:
    extension = Path(name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("unsupported_source_type")
    return extension


def _file_id(root_key: str, relative: str, digest: str) -> str:
    """Create an opaque stable approved-file identifier without exposing paths."""
    return hashlib.sha256(f"{root_key}:{relative}:{digest}".encode()).hexdigest()


def _approved_roots(settings: Settings) -> list[tuple[str, Path]]:
    raw = settings.workspace_roots.strip()
    data_root = settings.data_dir.expanduser().resolve()
    if not raw:
        return [("data", data_root)]
    roots: list[tuple[str, Path]] = []
    for index, value in enumerate(raw.split(",")[:8]):
        path = Path(value.strip()).expanduser()
        if not path.is_absolute():
            path = (data_root / path).resolve()
            if path != data_root and data_root not in path.parents:
                continue
        roots.append((f"root-{index + 1}", path))
    return roots or [("data", data_root)]


def discover_approved_files(settings: Settings, *, limit: int = 100) -> list[dict[str, object]]:
    """Discover bounded UTF-8 text files beneath server-configured roots."""
    result: list[dict[str, object]] = []
    for root_key, configured in _approved_roots(settings):
        root = configured.resolve()
        if not root.is_dir():
            continue
        for current, directories, filenames in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            directories[:] = [name for name in directories if _safe_name(name) and not (current_path / name).is_symlink()]
            for filename in filenames:
                if len(result) >= max(1, min(limit, 100)):
                    return result
                path = current_path / filename
                if path.is_symlink() or not _safe_name(filename):
                    continue
                try:
                    extension = _extension(filename)
                    stat = path.stat()
                    if stat.st_size <= 0 or stat.st_size > MAX_UPLOAD_BYTES:
                        continue
                    size, digest = _hash_file(path)
                    _detect_text(path, extension)
                    relative = path.relative_to(root).as_posix()
                except (OSError, ValueError):
                    continue
                result.append({"file_id": _file_id(root_key, relative, digest), "root_key": root_key, "relative_path": relative, "name": filename, "mime_type": ALLOWED_EXTENSIONS[extension], "size_bytes": size, "sha256": digest})
    return result


def _resolve_approved_file(settings: Settings, file_id: str) -> tuple[Path, dict[str, object]] | None:
    """Resolve an opaque file identifier by re-scanning and re-validating roots."""
    for item in discover_approved_files(settings, limit=100):
        if item["file_id"] != file_id:
            continue
        root = dict(_approved_roots(settings))[str(item["root_key"])]
        candidate = (root / str(item["relative_path"])).resolve()
        if candidate != root and root in candidate.parents and candidate.is_file():
            return candidate, item
    return None


def _job_for_source(db: OrmSession, source_id: str) -> Job | None:
    return db.scalar(select(Job).where(Job.job_type == SOURCE_JOB_TYPE, Job.payload_json == source_id, Job.status.in_(("queued", "processing"))).order_by(Job.created_at.desc()))


def _source_response_fields(source: Source) -> dict[str, object]:
    return {"id": source.id, "kind": source.kind, "title": source.title, "original_name": source.original_name, "mime_type": source.mime_type, "size_bytes": source.size_bytes, "sha256": source.sha256, "status": source.status, "current_version": source.current_version, "last_ingested_at": source.last_ingested_at, "last_error_code": source.last_error_code, "created_at": source.created_at, "updated_at": source.updated_at, "archived_at": source.archived_at}


def create_upload(db: OrmSession, settings: Settings, user_id: str, filename: str, content: bytes, title: str | None = None) -> Source:
    """Store a bounded server-named UTF-8 text upload and queue ingestion."""
    if not _safe_name(filename):
        raise ValueError("unsafe_source_name")
    extension = _extension(filename)
    if extension == ".pdf":
        raise ValueError("pdf_ingestion_not_enabled")
    if len(content) == 0 or len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("source_exceeds_size_limit")
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("source_must_be_utf8_text") from exc
    if not text_content.strip():
        raise ValueError("source_must_not_be_empty")
    count = db.scalar(select(Source.id).where(Source.user_id == user_id, Source.deleted_at.is_(None)).limit(MAX_SOURCE_COUNT + 1))
    if count is not None and db.query(Source).filter(Source.user_id == user_id, Source.deleted_at.is_(None)).count() >= MAX_SOURCE_COUNT:
        raise ValueError("source_quota_exceeded")
    digest = hashlib.sha256(content).hexdigest()
    existing = db.scalar(select(Source).where(Source.user_id == user_id, Source.sha256 == digest, Source.deleted_at.is_(None)))
    if existing is not None:
        return existing
    source_id = str(uuid4())
    path = _source_root(settings) / f"{source_id}{extension}"
    path.write_bytes(content)
    source = Source(user_id=user_id, kind="upload", title=(title or Path(filename).stem)[:160], original_name=filename[:255], stored_path=path.name, mime_type=ALLOWED_EXTENSIONS[extension], size_bytes=len(content), sha256=digest, status="processing", current_version=0)
    db.add(source)
    db.flush()
    db.add(Job(job_type=SOURCE_JOB_TYPE, status="queued", payload_json=source.id, available_at=utc_now(), idempotency_key=f"source:{source.id}"))
    add_audit_event(db, action="sources.upload", result="success", actor_user_id=user_id, target=source.id, metadata={"kind": "upload", "size_bytes": len(content), "mime_type": source.mime_type})
    db.commit()
    db.refresh(source)
    return source


def _read_approved_file(path: Path, info: dict[str, object]) -> bytes:
    """Read an approved file without following path components on Linux."""
    if sys.platform != "win32" and hasattr(os, "O_NOFOLLOW"):
        parent = path.parent
        parent_parts = parent.parts[1:] if parent.is_absolute() else parent.parts
        descriptor = os.open(os.sep, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            for component in parent_parts:
                next_descriptor = os.open(component, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_NOFOLLOW, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = next_descriptor
            file_descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=descriptor)
        finally:
            os.close(descriptor)
    else:
        no_follow = getattr(os, "O_NOFOLLOW", 0)
        binary = getattr(os, "O_BINARY", 0)
        file_descriptor = os.open(path, os.O_RDONLY | binary | no_follow)
    try:
        file_stat = os.fstat(file_descriptor)
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_size <= 0 or file_stat.st_size > MAX_UPLOAD_BYTES:
            raise ValueError("source_exceeds_size_limit")
        digest = hashlib.sha256()
        blocks: list[bytes] = []
        size = 0
        with os.fdopen(file_descriptor, "rb") as stream:
            file_descriptor = -1
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(block)
                if size > MAX_UPLOAD_BYTES:
                    raise ValueError("source_exceeds_size_limit")
                digest.update(block)
                blocks.append(block)
        if size != int(info["size_bytes"]) or digest.hexdigest() != str(info["sha256"]):
            raise ValueError("approved_file_changed")
        return b"".join(blocks)
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)


def import_approved_file(db: OrmSession, settings: Settings, user_id: str, payload: SourceImportRequest) -> Source:
    """Copy one revalidated approved-root text file into private source storage."""
    resolved = _resolve_approved_file(settings, payload.file_id)
    if resolved is None:
        raise ValueError("approved_file_not_found")
    path, info = resolved
    try:
        content = _read_approved_file(path, info)
    except (OSError, RuntimeError) as exc:
        raise ValueError("approved_file_not_found") from exc
    source = create_upload(db, settings, user_id, str(info["name"]), content, payload.title)
    source.kind = "approved_file"
    db.commit()
    return source


def list_sources(db: OrmSession, user_id: str, *, status_filter: str = "active", limit: int = 50, cursor: str | None = None) -> list[Source]:
    statement = select(Source).where(Source.user_id == user_id, Source.deleted_at.is_(None))
    if status_filter == "archived":
        statement = statement.where(Source.status == "archived")
    elif status_filter != "all":
        statement = statement.where(Source.status != "archived")
    if cursor:
        statement = statement.where(Source.id < cursor)
    return list(db.scalars(statement.order_by(Source.updated_at.desc(), Source.id.desc()).limit(max(1, min(limit, 100)))))


def get_source(db: OrmSession, user_id: str, source_id: str) -> Source | None:
    return db.scalar(select(Source).where(Source.id == source_id, Source.user_id == user_id, Source.deleted_at.is_(None)))


def archive_source(db: OrmSession, user_id: str, source_id: str) -> Source | None:
    source = get_source(db, user_id, source_id)
    if source is None:
        return None
    source.status = "archived"
    source.archived_at = utc_now()
    add_audit_event(db, action="sources.archive", result="success", actor_user_id=user_id, target=source.id)
    db.commit()
    return source


def restore_source(db: OrmSession, user_id: str, source_id: str) -> Source | None:
    source = get_source(db, user_id, source_id)
    if source is None:
        return None
    source.status = "ready" if source.current_version else "processing"
    source.archived_at = None
    add_audit_event(db, action="sources.restore", result="success", actor_user_id=user_id, target=source.id)
    db.commit()
    return source


def delete_source(db: OrmSession, user_id: str, source_id: str) -> Source | None:
    source = get_source(db, user_id, source_id)
    if source is None:
        return None
    source.deleted_at = utc_now()
    source.status = "archived"
    add_audit_event(db, action="sources.delete", result="success", actor_user_id=user_id, target=source.id)
    db.commit()
    return source


def reindex_source(db: OrmSession, user_id: str, source_id: str) -> Source | None:
    source = get_source(db, user_id, source_id)
    if source is None:
        return None
    job = _job_for_source(db, source.id)
    if job is None:
        job = Job(job_type=SOURCE_JOB_TYPE, status="queued", payload_json=source.id, available_at=utc_now(), idempotency_key=f"source:{source.id}:reindex:{uuid4()}")
        db.add(job)
    source.status = "processing"
    source.last_error_code = None
    db.commit()
    return source


def _parse_source_file(settings: Settings, source: Source) -> tuple[str, str]:
    path = _source_root(settings) / source.stored_path
    if not path.is_file():
        raise ValueError("source_file_missing")
    size, digest = _hash_file(path)
    if digest != source.sha256 or size != source.size_bytes:
        raise ValueError("source_integrity_mismatch")
    return _detect_text(path, Path(source.original_name).suffix.lower()), "utf8-text"


def process_source_ingestion(db: OrmSession, settings: Settings, *, batch_size: int = 2) -> int:
    """Process a bounded set of source ingestion jobs with lease recovery."""
    now = datetime.now(UTC)
    jobs = db.scalars(select(Job).where(Job.job_type == SOURCE_JOB_TYPE, Job.status.in_(("queued", "processing")), Job.available_at <= now, Job.attempts < 3, (Job.locked_until.is_(None) | (Job.locked_until <= now))).order_by(Job.created_at).limit(max(1, min(batch_size, 4)))).all()
    processed = 0
    for job in jobs:
        job.status = "processing"
        job.attempts += 1
        job.locked_until = now.replace(microsecond=0)
        job.locked_until = datetime.fromtimestamp(now.timestamp() + 120, UTC)
        db.commit()
        source = db.get(Source, job.payload_json or "")
        try:
            if source is None or source.deleted_at is not None:
                raise ValueError("source_not_found")
            content, parser = _parse_source_file(settings, source)
            source.current_version += 1
            version = SourceVersion(source_id=source.id, user_id=source.user_id, version=source.current_version, content_hash=hashlib.sha256(content.encode()).hexdigest(), content_length=len(content), parser=parser, parser_version="1", created_at=utc_now())
            db.add(version)
            db.flush()
            for index, (start, end, chunk_content) in enumerate(_split_chunks(content)[:MAX_CHUNKS]):
                db.add(SourceChunk(source_id=source.id, source_version_id=version.id, user_id=source.user_id, chunk_index=index, content=chunk_content, content_hash=hashlib.sha256(chunk_content.encode()).hexdigest(), start_offset=start, end_offset=end, source_version=version.version))
            source.status = "ready"
            source.last_ingested_at = utc_now()
            source.last_error_code = None
            job.status = "completed"
            job.completed_at = utc_now()
            job.locked_until = None
            add_audit_event(db, action="sources.ingest", result="success", actor_user_id=source.user_id, target=source.id, metadata={"version": version.version, "parser": parser})
        except (OSError, ValueError, UnicodeError):
            source = db.get(Source, job.payload_json or "")
            if source is not None:
                source.status = "failed"
                source.last_error_code = "source_ingestion_failed"
            job.status = "failed" if job.attempts >= 3 else "queued"
            job.last_error_code = "source_ingestion_failed"
            job.available_at = datetime.fromtimestamp(now.timestamp() + (2 ** job.attempts) * 30, UTC)
            job.locked_until = None
            if source is not None:
                add_audit_event(db, action="sources.ingest", result="failure", actor_user_id=source.user_id, target=source.id, metadata={"error_code": job.last_error_code})
        db.commit()
        processed += 1
    return processed


def source_versions(db: OrmSession, user_id: str, source_id: str) -> list[SourceVersion] | None:
    source = get_source(db, user_id, source_id)
    if source is None:
        return None
    return list(db.scalars(select(SourceVersion).where(SourceVersion.source_id == source.id, SourceVersion.user_id == user_id).order_by(SourceVersion.version.desc()).limit(20)))


def source_chunks(db: OrmSession, user_id: str, source_id: str) -> list[SourceChunk] | None:
    source = get_source(db, user_id, source_id)
    if source is None:
        return None
    return list(db.scalars(select(SourceChunk).where(SourceChunk.source_id == source.id, SourceChunk.user_id == user_id, SourceChunk.source_version == source.current_version).order_by(SourceChunk.chunk_index).limit(MAX_CHUNKS)))


def source_response(source: Source) -> dict[str, object]:
    return _source_response_fields(source)
