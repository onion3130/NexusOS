"""Authenticated external source ingestion routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as OrmSession

from app.core.config import Settings, get_settings
from app.db.models import Source, SourceChunk, SourceVersion
from app.db.session import get_db
from app.modules.identity.dependencies import AuthContext, get_auth_context, require_csrf, require_permission
from app.modules.sources.schemas import ApprovedFileListResponse, ApprovedFileResponse, SourceChunksResponse, SourceImportRequest, SourceListResponse, SourceResponse, SourceVersionResponse, SourceVersionsResponse
from app.modules.sources.sync import configure_sync, disable_sync, queue_manual_sync, sync_response
from app.modules.sources.sync_schemas import SourceSyncJobResponse, SourceSyncResponse, SourceSyncUpdate
from app.modules.sources.service import archive_source, create_upload, delete_source, discover_approved_files, get_source, import_approved_file, list_sources, restore_source, reindex_source, source_chunks, source_response, source_versions

router = APIRouter(prefix="/api/v1/sources", tags=["sources"])


def _response(source: Source) -> SourceResponse:
    return SourceResponse.model_validate(source_response(source))


def _version_response(item: SourceVersion) -> SourceVersionResponse:
    return SourceVersionResponse(id=item.id, version=item.version, content_hash=item.content_hash, content_length=item.content_length, parser=item.parser, parser_version=item.parser_version, created_at=item.created_at)


def _chunk_response(item: SourceChunk):
    from app.modules.sources.schemas import SourceChunkResponse
    return SourceChunkResponse(id=item.id, source_version_id=item.source_version_id, chunk_index=item.chunk_index, content=item.content, content_hash=item.content_hash, start_offset=item.start_offset, end_offset=item.end_offset, source_version=item.source_version, created_at=item.created_at)


@router.get("", response_model=SourceListResponse)
def list_all(status_filter: str = "active", limit: int = 50, cursor: str | None = None, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)):
    require_permission("sources.read", context)
    if status_filter not in {"active", "archived", "all"}:
        raise HTTPException(422, "invalid source status filter")
    items = list_sources(db, context.user.id, status_filter=status_filter, limit=limit, cursor=cursor)
    return SourceListResponse(items=[_response(item) for item in items], next_cursor=items[-1].id if items and len(items) == min(max(limit, 1), 100) else None)


@router.post("/upload", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def upload(request: Request, settings: Settings = Depends(get_settings), db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)):
    require_csrf(request, context)
    require_permission("sources.write", context)
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > 10 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="source_exceeds_size_limit")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid_content_length") from exc
    filename = request.headers.get("X-Source-Filename", "source.txt")
    title = request.headers.get("X-Source-Title")
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="source_exceeds_size_limit")
        chunks.append(chunk)
    try:
        return _response(create_upload(db, settings, context.user.id, filename, b"".join(chunks), title))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/approved-files", response_model=ApprovedFileListResponse)
def approved_files(settings: Settings = Depends(get_settings), context: AuthContext = Depends(get_auth_context)):
    require_permission("sources.read", context)
    return ApprovedFileListResponse(items=[ApprovedFileResponse.model_validate(item) for item in discover_approved_files(settings)])


@router.post("/import-approved-file", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def import_file(payload: SourceImportRequest, request: Request, settings: Settings = Depends(get_settings), db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)):
    require_csrf(request, context)
    require_permission("sources.write", context)
    try:
        return _response(import_approved_file(db, settings, context.user.id, payload))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/{source_id}/sync", response_model=SourceSyncResponse | None)
def get_sync(source_id: str, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)):
    require_permission("sources.read", context)
    source = get_source(db, context.user.id, source_id)
    if source is None:
        raise HTTPException(404, "Source not found")
    return sync_response(source.sync_config)


@router.post("/{source_id}/sync", response_model=SourceSyncResponse)
def update_sync(source_id: str, payload: SourceSyncUpdate, request: Request, settings: Settings = Depends(get_settings), db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)):
    require_csrf(request, context)
    require_permission("sources.write", context)
    source = get_source(db, context.user.id, source_id)
    if source is None:
        raise HTTPException(404, "Source not found")
    try:
        return sync_response(configure_sync(db, settings, context.user.id, source, enabled=payload.enabled, interval_seconds=payload.interval_seconds))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/{source_id}/sync", response_model=SourceSyncResponse)
def remove_sync(source_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)):
    require_csrf(request, context)
    require_permission("sources.write", context)
    source = get_source(db, context.user.id, source_id)
    if source is None:
        raise HTTPException(404, "Source not found")
    result = disable_sync(db, context.user.id, source)
    if result is None:
        raise HTTPException(404, "Source synchronization not configured")
    return sync_response(result)


@router.post("/{source_id}/sync-now", response_model=SourceSyncJobResponse, status_code=status.HTTP_202_ACCEPTED)
def sync_now(source_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)):
    require_csrf(request, context)
    require_permission("sources.write", context)
    source = get_source(db, context.user.id, source_id)
    if source is None:
        raise HTTPException(404, "Source not found")
    try:
        job = queue_manual_sync(db, context.user.id, source)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return SourceSyncJobResponse(id=job.id, source_id=source.id, status=job.status, attempts=job.attempts, error_code=job.last_error_code, created_at=job.created_at, completed_at=job.completed_at)


@router.get("/{source_id}", response_model=SourceResponse)
def get_one(source_id: str, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)):
    require_permission("sources.read", context)
    source = get_source(db, context.user.id, source_id)
    if source is None: raise HTTPException(404, "Source not found")
    return _response(source)


@router.get("/{source_id}/versions", response_model=SourceVersionsResponse)
def versions(source_id: str, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)):
    require_permission("sources.read", context)
    items = source_versions(db, context.user.id, source_id)
    if items is None: raise HTTPException(404, "Source not found")
    return SourceVersionsResponse(items=[_version_response(item) for item in items])


@router.get("/{source_id}/chunks", response_model=SourceChunksResponse)
def chunks(source_id: str, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)):
    require_permission("sources.read", context)
    items = source_chunks(db, context.user.id, source_id)
    if items is None: raise HTTPException(404, "Source not found")
    return SourceChunksResponse(items=[_chunk_response(item) for item in items])


@router.post("/{source_id}/archive", response_model=SourceResponse)
def archive(source_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)):
    require_csrf(request, context); require_permission("sources.delete", context)
    result = archive_source(db, context.user.id, source_id)
    if result is None: raise HTTPException(404, "Source not found")
    return _response(result)


@router.post("/{source_id}/restore", response_model=SourceResponse)
def restore(source_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)):
    require_csrf(request, context); require_permission("sources.write", context)
    result = restore_source(db, context.user.id, source_id)
    if result is None: raise HTTPException(404, "Source not found")
    return _response(result)


@router.post("/{source_id}/reindex", response_model=SourceResponse)
def reindex(source_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)):
    require_csrf(request, context); require_permission("sources.write", context)
    result = reindex_source(db, context.user.id, source_id)
    if result is None: raise HTTPException(404, "Source not found")
    return _response(result)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(source_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)):
    require_csrf(request, context); require_permission("sources.delete", context)
    if delete_source(db, context.user.id, source_id) is None: raise HTTPException(404, "Source not found")
