"""Canonical note services and derived search/retrieval maintenance."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session as OrmSession, selectinload

from app.db.base import utc_now
from app.db.models import Job, Note, NoteChunk, NoteSearchDocument, Tag
from app.modules.identity.service import add_audit_event
from app.modules.notes.schemas import NoteCreate, NoteUpdate
from app.modules.tasks.service import _fingerprint, _mutation_key, _prior_mutation, _record_mutation

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 120


def _load_note(db: OrmSession, user_id: str, note_id: str) -> Note | None:
    return db.scalar(
        select(Note).where(Note.id == note_id, Note.user_id == user_id, Note.deleted_at.is_(None)).options(selectinload(Note.tags))
    )


def _tags(db: OrmSession, user_id: str, names: list[str]) -> list[Tag]:
    result: list[Tag] = []
    for name in names:
        normalized = name.casefold()
        tag = db.scalar(select(Tag).where(Tag.user_id == user_id, Tag.normalized_name == normalized))
        if tag is None:
            tag = Tag(user_id=user_id, name=name, normalized_name=normalized)
            db.add(tag)
            db.flush()
        result.append(tag)
    return result


def _split_chunks(content: str) -> list[tuple[int, int, str]]:
    """Split note content deterministically into bounded overlapping chunks."""
    if not content:
        return []
    chunks: list[tuple[int, int, str]] = []
    start = 0
    while start < len(content):
        end = min(len(content), start + CHUNK_SIZE)
        if end < len(content):
            boundary = content.rfind("\n\n", start + CHUNK_SIZE // 2, end)
            if boundary > start:
                end = boundary
        piece = content[start:end].strip()
        if piece:
            left = start + (len(content[start:end]) - len(content[start:end].lstrip()))
            right = left + len(piece)
            chunks.append((left, right, piece))
        if end >= len(content):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def _sync_search_document(db: OrmSession, note: Note) -> None:
    """Replace one derived projection and its FTS row in the current transaction."""
    document = db.scalar(select(NoteSearchDocument).where(NoteSearchDocument.note_id == note.id))
    tags_text = " ".join(tag.name for tag in note.tags)
    if document is None:
        document = NoteSearchDocument(note_id=note.id, title=note.title, content=note.content, tags_text=tags_text, indexed_version=note.content_version)
        db.add(document)
        db.flush()
    else:
        db.execute(text("DELETE FROM notes_fts WHERE rowid = :rowid"), {"rowid": document.id})
        document.title = note.title
        document.content = note.content
        document.tags_text = tags_text
        document.indexed_version = note.content_version
        document.updated_at = utc_now()
    db.execute(
        text("INSERT INTO notes_fts(rowid, title, content, tags) VALUES (:rowid, :title, :content, :tags)"),
        {"rowid": document.id, "title": note.title, "content": note.content, "tags": tags_text},
    )


def _sync_chunks(db: OrmSession, note: Note) -> None:
    """Regenerate current-version chunks from canonical note content."""
    db.execute(delete(NoteChunk).where(NoteChunk.note_id == note.id))
    for index, (start, end, content) in enumerate(_split_chunks(note.content)):
        db.add(NoteChunk(note_id=note.id, user_id=note.user_id, chunk_index=index, content=content, content_hash=hashlib.sha256(content.encode()).hexdigest(), start_offset=start, end_offset=end, source_version=note.content_version))


def create_note(db: OrmSession, user_id: str, payload: NoteCreate, idempotency_key: str | None = None) -> Note:
    """Create a note and all derived retrieval data atomically."""
    serialized = payload.model_dump(mode="json")
    prior = _prior_mutation(db, user_id, "note-create", idempotency_key, serialized)
    if prior:
        existing = _load_note(db, user_id, prior[0])
        if existing:
            return existing
    note = Note(user_id=user_id, title=payload.title, content=payload.content, status=payload.status, tags=_tags(db, user_id, payload.tags))
    db.add(note)
    db.flush()
    _sync_search_document(db, note)
    _sync_chunks(db, note)
    _record_mutation(db, user_id, "note-create", idempotency_key, note.id, serialized)
    add_audit_event(db, action="notes.create", result="success", actor_user_id=user_id, target=note.id, metadata={"content_version": note.content_version})
    db.commit()
    return _load_note(db, user_id, note.id)  # type: ignore[return-value]


def list_notes(db: OrmSession, user_id: str, *, status: str = "active", tag: str | None = None, limit: int = 50, cursor: str | None = None) -> list[Note]:
    """List owned, non-deleted notes with bounded filters."""
    statement = select(Note).where(Note.user_id == user_id, Note.deleted_at.is_(None)).options(selectinload(Note.tags))
    if status != "all":
        statement = statement.where(Note.status == status)
    if tag:
        statement = statement.join(Note.tags).where(Tag.user_id == user_id, Tag.normalized_name == tag.casefold())
    if cursor:
        statement = statement.where(Note.id < cursor)
    return list(db.scalars(statement.order_by(Note.updated_at.desc()).limit(max(1, min(limit, 100)))))


def get_note(db: OrmSession, user_id: str, note_id: str) -> Note | None:
    """Return one owned live note."""
    return _load_note(db, user_id, note_id)


def update_note(db: OrmSession, user_id: str, note_id: str, payload: NoteUpdate, idempotency_key: str | None = None) -> Note | None:
    """Update a note and regenerate only the derived data affected by changes."""
    changes = payload.model_dump(mode="json", exclude_unset=True)
    mutation_payload = {"note_id": note_id, "changes": changes}
    prior = _prior_mutation(db, user_id, "note-update", idempotency_key, mutation_payload)
    if prior:
        return _load_note(db, user_id, prior[0])
    note = _load_note(db, user_id, note_id)
    if note is None:
        return None
    source_changed = "title" in changes or "content" in changes
    tags_changed = "tags" in changes
    if "title" in changes:
        note.title = changes["title"]
    if "content" in changes:
        note.content = changes["content"]
    if "status" in changes:
        note.status = changes["status"]
        note.archived_at = utc_now() if note.status == "archived" else None
    if tags_changed:
        note.tags = _tags(db, user_id, changes["tags"])
    if source_changed:
        note.content_version += 1
    db.flush()
    if source_changed or tags_changed:
        _sync_search_document(db, note)
    if source_changed:
        _sync_chunks(db, note)
    _record_mutation(db, user_id, "note-update", idempotency_key, note.id, mutation_payload)
    add_audit_event(db, action="notes.update", result="success", actor_user_id=user_id, target=note.id, metadata={"fields": sorted(changes), "content_version": note.content_version})
    db.commit()
    return _load_note(db, user_id, note.id)


def archive_note(db: OrmSession, user_id: str, note_id: str, idempotency_key: str | None = None) -> Note | None:
    """Archive one owned note."""
    return update_note(db, user_id, note_id, NoteUpdate(status="archived"), idempotency_key)


def restore_note(db: OrmSession, user_id: str, note_id: str, idempotency_key: str | None = None) -> Note | None:
    """Restore one owned note."""
    return update_note(db, user_id, note_id, NoteUpdate(status="active"), idempotency_key)


def delete_note(db: OrmSession, user_id: str, note_id: str, idempotency_key: str | None = None) -> Note | None:
    """Soft-delete one owned note while retaining its audit/source history."""
    prior = _prior_mutation(db, user_id, "note-delete", idempotency_key, {"note_id": note_id})
    if prior:
        return db.scalar(select(Note).where(Note.id == prior[0], Note.user_id == user_id))
    note = _load_note(db, user_id, note_id)
    if note is None:
        return None
    note.deleted_at = utc_now()
    note.status = "archived"
    db.flush()
    db.execute(text("DELETE FROM notes_fts WHERE rowid = (SELECT id FROM note_search_documents WHERE note_id = :note_id)"), {"note_id": note.id})
    _record_mutation(db, user_id, "note-delete", idempotency_key, note.id, {"note_id": note_id})
    add_audit_event(db, action="notes.delete", result="success", actor_user_id=user_id, target=note.id)
    db.commit()
    return note


def list_chunks(db: OrmSession, user_id: str, note_id: str) -> list[NoteChunk] | None:
    """Return current chunks only for one owned note."""
    note = _load_note(db, user_id, note_id)
    if note is None:
        return None
    return list(db.scalars(select(NoteChunk).where(NoteChunk.note_id == note.id, NoteChunk.user_id == user_id, NoteChunk.source_version == note.content_version).order_by(NoteChunk.chunk_index)))
