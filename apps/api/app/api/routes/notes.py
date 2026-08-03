"""Authenticated notes and source-aware search routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as OrmSession

from app.db.models import Note, NoteChunk
from app.db.session import get_db
from app.modules.identity.dependencies import AuthContext, get_auth_context, require_csrf, require_permission
from app.modules.notes.retrieval import retrieve_note_chunks
from app.modules.notes.schemas import NoteChunksResponse, NoteCreate, NoteListResponse, NoteResponse, NoteUpdate, RetrievalChunkResponse, RetrievalResult, SearchResponse
from app.modules.notes.search import search_notes
from app.modules.notes.service import archive_note, create_note, delete_note, get_note, list_chunks, list_notes, restore_note, update_note

router = APIRouter(prefix="/api/v1", tags=["notes"])


def _response(note: Note) -> NoteResponse:
    return NoteResponse(id=note.id, title=note.title, content=note.content, status=note.status, created_at=note.created_at, updated_at=note.updated_at, archived_at=note.archived_at, content_version=note.content_version, tags=[tag.name for tag in note.tags])


def _chunk_response(item: NoteChunk) -> RetrievalChunkResponse:
    return RetrievalChunkResponse(id=item.id, note_id=item.note_id, chunk_index=item.chunk_index, content=item.content, content_hash=item.content_hash, start_offset=item.start_offset, end_offset=item.end_offset, source_version=item.source_version, created_at=item.created_at, updated_at=item.updated_at)


@router.get("/notes", response_model=NoteListResponse)
def list_all(status_filter: str = "active", tag: str | None = None, limit: int = 50, cursor: str | None = None, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> NoteListResponse:
    require_permission("notes.read", context)
    if status_filter not in {"active", "archived", "all"}:
        raise HTTPException(status_code=422, detail="invalid note status filter")
    items = list_notes(db, context.user.id, status=status_filter, tag=tag, limit=limit, cursor=cursor)
    return NoteListResponse(items=[_response(item) for item in items], next_cursor=items[-1].id if len(items) == min(max(limit, 1), 100) else None)


@router.post("/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
def create(payload: NoteCreate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> NoteResponse:
    require_csrf(request, context)
    require_permission("notes.write", context)
    try:
        return _response(create_note(db, context.user.id, payload, request.headers.get("Idempotency-Key")))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/notes/{note_id}", response_model=NoteResponse)
def get_one(note_id: str, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> NoteResponse:
    require_permission("notes.read", context)
    note = get_note(db, context.user.id, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return _response(note)


@router.patch("/notes/{note_id}", response_model=NoteResponse)
def update(note_id: str, payload: NoteUpdate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> NoteResponse:
    require_csrf(request, context)
    require_permission("notes.write", context)
    try:
        note = update_note(db, context.user.id, note_id, payload, request.headers.get("Idempotency-Key"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return _response(note)


def _transition(note_id: str, request: Request, db: OrmSession, context: AuthContext, action) -> NoteResponse:
    require_csrf(request, context)
    require_permission("notes.write", context)
    note = action(db, context.user.id, note_id, request.headers.get("Idempotency-Key"))
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return _response(note)


@router.post("/notes/{note_id}/archive", response_model=NoteResponse)
def archive(note_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> NoteResponse:
    return _transition(note_id, request, db, context, archive_note)


@router.post("/notes/{note_id}/restore", response_model=NoteResponse)
def restore(note_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> NoteResponse:
    return _transition(note_id, request, db, context, restore_note)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(note_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> None:
    require_csrf(request, context)
    require_permission("notes.delete", context)
    if delete_note(db, context.user.id, note_id, request.headers.get("Idempotency-Key")) is None:
        raise HTTPException(status_code=404, detail="Note not found")


@router.get("/notes/{note_id}/chunks", response_model=NoteChunksResponse)
def chunks(note_id: str, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> NoteChunksResponse:
    require_permission("notes.read", context)
    items = list_chunks(db, context.user.id, note_id)
    if items is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return NoteChunksResponse(items=[_chunk_response(item) for item in items])


@router.get("/search", response_model=SearchResponse)
def search(q: str, tag: str | None = None, include_archived: bool = False, limit: int = 20, cursor: str | None = None, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> SearchResponse:
    require_permission("notes.read", context)
    try:
        items = search_notes(db, context.user.id, q, tag=tag, include_archived=include_archived, limit=limit, cursor=cursor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SearchResponse(items=items, next_cursor=items[-1].source_id if len(items) == min(max(limit, 1), 50) else None)


@router.get("/search/retrieve", response_model=list[RetrievalResult])
def retrieve(q: str, limit: int = 8, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> list[RetrievalResult]:
    require_permission("notes.read", context)
    return retrieve_note_chunks(db, context.user.id, q, limit=limit)
