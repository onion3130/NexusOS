"""Authenticated media library routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as OrmSession

from app.core.config import get_settings
from app.db.models import MediaItem
from app.db.session import get_db
from app.modules.identity.dependencies import AuthContext, get_auth_context, require_csrf, require_permission
from app.modules.media.schemas import MediaItemResponse, MediaListResponse, MediaRescanResponse
from app.modules.media.service import configured_media_roots, list_media_items, queue_media_rescan, resolve_media_path, resolve_thumbnail_path

router = APIRouter(prefix="/api/v1/media", tags=["media"])

_THUMBNAIL_CONTENT_TYPE = "image/jpeg"


def _item_response(item: MediaItem) -> MediaItemResponse:
    return MediaItemResponse(id=item.id, root_key=item.root_key, relative_path=item.relative_path, file_name=item.file_name, extension=item.extension, mime_type=item.mime_type, size_bytes=item.size_bytes, sha256=item.sha256, width=item.width, height=item.height, has_thumbnail=item.thumbnail_path is not None, indexed_at=item.indexed_at, updated_at=item.updated_at)


@router.get("/items", response_model=MediaListResponse)
def items(extension: str | None = None, mime_type: str | None = None, folder: str | None = None, limit: int = 100, cursor: str | None = None, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> MediaListResponse:
    require_permission("media.read", context)
    result = list_media_items(db, extension=extension, mime_type=mime_type, folder=folder, limit=limit, cursor=cursor)
    return MediaListResponse(items=[_item_response(item) for item in result], next_cursor=result[-1].id if len(result) == min(max(limit, 1), 200) else None)


@router.post("/rescan", response_model=MediaRescanResponse)
def rescan(request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> MediaRescanResponse:
    require_csrf(request, context)
    require_permission("media.write", context)
    roots = configured_media_roots(get_settings())
    queued, job_id = queue_media_rescan(db)
    return MediaRescanResponse(queued=queued, job_id=job_id, roots_configured=bool(roots))


@router.get("/items/{item_id}/thumbnail")
def thumbnail(item_id: str, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> Response:
    require_permission("media.read", context)
    item = db.get(MediaItem, item_id)
    if item is None or item.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media item not found")
    path = resolve_thumbnail_path(get_settings().data_dir, item)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail unavailable")
    return FileResponse(path, media_type=_THUMBNAIL_CONTENT_TYPE, headers={"Cache-Control": "private, max-age=86400"})


@router.get("/items/{item_id}/stream")
def stream(item_id: str, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> Response:
    require_permission("media.read", context)
    resolved = resolve_media_path(db, item_id, configured_media_roots(get_settings()))
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media item not found")
    path, item = resolved
    return FileResponse(path, media_type=item.mime_type, filename=item.file_name, headers={"Cache-Control": "private, max-age=3600"})
