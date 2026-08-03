"""Provider-neutral source-aware retrieval contracts for future RAG."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession, selectinload

from app.db.models import Note, NoteChunk
from app.modules.notes.schemas import RetrievalResult
from app.modules.notes.search import _TOKEN_RE


def retrieve_note_chunks(db: OrmSession, user_id: str, query: str, *, limit: int = 8) -> list[RetrievalResult]:
    """Return bounded, provenance-preserving lexical chunks without model calls."""
    terms = [term.casefold() for term in _TOKEN_RE.findall(query)[:32]]
    if not terms:
        return []
    rows = db.execute(
        select(NoteChunk, Note).join(Note, Note.id == NoteChunk.note_id).where(NoteChunk.user_id == user_id, Note.user_id == user_id, Note.status == "active", Note.deleted_at.is_(None)).options(selectinload(Note.tags)).order_by(Note.updated_at.desc()).limit(200)
    ).all()
    ranked: list[tuple[int, NoteChunk, Note]] = []
    for chunk, note in rows:
        haystack = chunk.content.casefold()
        score = sum(haystack.count(term) for term in terms)
        if score:
            ranked.append((score, chunk, note))
    ranked.sort(key=lambda item: (-item[0], item[2].updated_at), reverse=False)
    return [RetrievalResult(source_type="note", source_id=note.id, chunk_id=chunk.id, title=note.title, excerpt=chunk.content[:1200], score=float(-score), source_version=chunk.source_version, updated_at=note.updated_at, metadata={"content_hash": chunk.content_hash, "chunk_index": chunk.chunk_index, "tags": [tag.name for tag in note.tags]}) for score, chunk, note in ranked[:max(1, min(limit, 20))]]
