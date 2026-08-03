"""Bounded, ownership-safe SQLite FTS5 search for notes."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session as OrmSession

from app.db.models import Note, NoteChunk, NoteSearchDocument, Tag
from app.modules.notes.schemas import SearchResult

MAX_QUERY_LENGTH = 200
_TOKEN_RE = re.compile(r"[\w\-']+", re.UNICODE)


def normalize_query(query: str) -> str:
    """Convert ordinary user text into a safe FTS5 phrase query."""
    normalized = " ".join(query.strip().split())[:MAX_QUERY_LENGTH]
    tokens = _TOKEN_RE.findall(normalized)
    if not tokens:
        raise ValueError("search query must contain searchable text")
    return " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens[:32])


def fts5_available(db: OrmSession) -> bool:
    """Return whether the configured SQLite runtime supports FTS5."""
    try:
        db.execute(text("SELECT fts5('test')"))
        return True
    except Exception:
        db.rollback()
        try:
            db.execute(text("SELECT 1 FROM notes_fts LIMIT 1"))
            return True
        except Exception:
            db.rollback()
            return False


def search_notes(db: OrmSession, user_id: str, query: str, *, tag: str | None = None, include_archived: bool = False, limit: int = 20, cursor: str | None = None) -> list[SearchResult]:
    """Search only owned canonical notes through the derived FTS projection."""
    match = normalize_query(query)
    bounded_limit = max(1, min(limit, 50))
    statement = """
        SELECT d.note_id, d.id AS document_id, d.title, d.content, d.tags_text,
               d.indexed_version, d.updated_at, bm25(notes_fts, 5.0, 1.0, 2.0) AS score
        FROM notes_fts
        JOIN note_search_documents d ON d.id = notes_fts.rowid
        JOIN notes n ON n.id = d.note_id
        WHERE notes_fts MATCH :match
          AND n.user_id = :user_id
          AND n.deleted_at IS NULL
    """
    params: dict[str, object] = {"match": match, "user_id": user_id, "limit": bounded_limit}
    if not include_archived:
        statement += " AND n.status = 'active'"
    if tag:
        statement += " AND EXISTS (SELECT 1 FROM note_tags nt JOIN tags t ON t.id = nt.tag_id WHERE nt.note_id = n.id AND t.user_id = :user_id AND t.normalized_name = :tag)"
        params["tag"] = tag.casefold()
    if cursor:
        statement += " AND d.note_id < :cursor"
        params["cursor"] = cursor
    statement += " ORDER BY score, d.updated_at DESC, d.note_id DESC LIMIT :limit"
    rows = db.execute(text(statement), params).mappings().all()
    results: list[SearchResult] = []
    for row in rows:
        note_tags = db.scalars(select(Tag.name).join(Tag.notes).where(Note.id == row["note_id"], Tag.user_id == user_id).order_by(Tag.name)).all()
        excerpt = _excerpt(str(row["content"]), query)
        chunk = db.scalar(select(NoteChunk).where(NoteChunk.note_id == row["note_id"], NoteChunk.user_id == user_id, NoteChunk.source_version == row["indexed_version"]).order_by(NoteChunk.chunk_index))
        results.append(SearchResult(source_type="note", source_id=str(row["note_id"]), chunk_id=chunk.id if chunk else None, title=str(row["title"]), excerpt=excerpt, score=float(row["score"]), updated_at=_timestamp(row["updated_at"]), source_version=int(row["indexed_version"]), tags=list(note_tags)))
    return results


def _timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value)).replace(tzinfo=None)


def _excerpt(content: str, query: str, max_length: int = 280) -> str:
    """Return plain text excerpt without trusting stored markup."""
    compact = " ".join(content.split())
    terms = [term.casefold() for term in _TOKEN_RE.findall(query)]
    position = next((compact.casefold().find(term) for term in terms if compact.casefold().find(term) >= 0), 0)
    start = max(0, position - 80)
    excerpt = compact[start:start + max_length]
    return ("…" if start else "") + excerpt + ("…" if start + max_length < len(compact) else "")
