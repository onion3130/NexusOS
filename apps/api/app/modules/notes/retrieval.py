"""Provider-neutral source-aware lexical, semantic, and hybrid retrieval."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession, selectinload

from app.core.config import Settings
from app.db.models import Note, NoteChunk, Source, SourceChunk
from app.modules.embeddings.gateway import embedding_gateway_from_settings
from app.modules.embeddings.service import semantic_candidates
from app.modules.notes.schemas import RetrievalResult
from app.modules.notes.search import _TOKEN_RE


def retrieve_note_chunks(db: OrmSession, user_id: str, query: str, *, limit: int = 8, include_archived: bool = False) -> list[RetrievalResult]:
    """Return bounded, provenance-preserving lexical chunks without model calls."""
    terms = [term.casefold() for term in _TOKEN_RE.findall(query)[:32]]
    if not terms:
        return []
    statement = select(NoteChunk, Note).join(Note, Note.id == NoteChunk.note_id).where(NoteChunk.user_id == user_id, Note.user_id == user_id, Note.deleted_at.is_(None)).options(selectinload(Note.tags)).order_by(Note.updated_at.desc()).limit(200)
    if not include_archived:
        statement = statement.where(Note.status == "active")
    rows = db.execute(statement).all()
    ranked: list[tuple[int, NoteChunk, Note]] = []
    for chunk, note in rows:
        haystack = chunk.content.casefold()
        score = sum(haystack.count(term) for term in terms)
        if score:
            ranked.append((score, chunk, note))
    ranked.sort(key=lambda item: (-item[0], -item[2].updated_at.timestamp()))
    return [_result(chunk, note, float(score), lexical_score=float(score), semantic_score=None, mode="lexical") for score, chunk, note in ranked[:max(1, min(limit, 20))]]


def _result(chunk: NoteChunk, note: Note, score: float, *, lexical_score: float | None, semantic_score: float | None, mode: str) -> RetrievalResult:
    """Build one bounded result with explicit provenance and ranking metadata."""
    return RetrievalResult(source_type="note", source_id=note.id, chunk_id=chunk.id, title=note.title, excerpt=chunk.content[:1200], score=score, lexical_score=lexical_score, semantic_score=semantic_score, retrieval_mode=mode, source_version=chunk.source_version, updated_at=note.updated_at, metadata={"content_hash": chunk.content_hash, "chunk_index": chunk.chunk_index, "tags": [tag.name for tag in note.tags]})


def retrieve_external_chunks(db: OrmSession, user_id: str, query: str, *, limit: int = 8, include_archived: bool = False) -> list[RetrievalResult]:
    """Return bounded lexical results from owned ingested external sources."""
    terms = [term.casefold() for term in _TOKEN_RE.findall(query)[:32]]
    if not terms:
        return []
    statement = select(SourceChunk, Source).join(Source, Source.id == SourceChunk.source_id).where(SourceChunk.user_id == user_id, Source.user_id == user_id, Source.deleted_at.is_(None), SourceChunk.source_version == Source.current_version).order_by(Source.updated_at.desc()).limit(500)
    if not include_archived:
        statement = statement.where(Source.status == "ready")
    else:
        statement = statement.where(Source.status.in_(("ready", "archived")))
    ranked: list[tuple[int, SourceChunk, Source]] = []
    for chunk, source in db.execute(statement).all():
        score = sum(chunk.content.casefold().count(term) for term in terms)
        if score:
            ranked.append((score, chunk, source))
    ranked.sort(key=lambda item: (-item[0], -item[2].updated_at.timestamp()))
    return [RetrievalResult(source_type="external_source", source_id=source.id, chunk_id=chunk.id, title=source.title, excerpt=chunk.content[:1200], score=float(score), lexical_score=float(score), semantic_score=None, retrieval_mode="lexical", source_version=chunk.source_version, updated_at=source.updated_at, metadata={"content_hash": chunk.content_hash, "chunk_index": chunk.chunk_index, "original_name": source.original_name}) for score, chunk, source in ranked[:max(1, min(limit, 20))]]


async def retrieve_semantic_chunks(db: OrmSession, settings: Settings, user_id: str, query: str, *, limit: int = 8, include_archived: bool = False) -> list[RetrievalResult]:
    """Embed one query and return owned semantic results, or lexical fallback."""
    bounded_limit = max(1, min(limit, 20))
    if settings.embedding_provider == "disabled":
        return retrieve_note_chunks(db, user_id, query, limit=bounded_limit, include_archived=include_archived)
    batch = await embedding_gateway_from_settings(settings).embed([query[: settings.embedding_max_chunk_length]])
    if not batch.vectors:
        return retrieve_note_chunks(db, user_id, query, limit=bounded_limit, include_archived=include_archived)
    ranked = semantic_candidates(db, user_id, batch.vectors[0], limit=bounded_limit, include_archived=include_archived)
    return [_result(chunk, note, score, lexical_score=None, semantic_score=score, mode="semantic") for score, _embedding, chunk, note in ranked]


async def retrieve_hybrid_chunks(db: OrmSession, settings: Settings, user_id: str, query: str, *, limit: int = 8, include_archived: bool = False, include_external: bool = False) -> list[RetrievalResult]:
    """Combine normalized lexical and semantic scores without requiring vectors."""
    bounded_limit = max(1, min(limit, 20))
    lexical = retrieve_note_chunks(db, user_id, query, limit=min(50, bounded_limit * 3), include_archived=include_archived)
    external = retrieve_external_chunks(db, user_id, query, limit=min(50, bounded_limit * 3), include_archived=include_archived) if include_external else []
    lexical = (lexical + external)[: max(1, min(50, bounded_limit * 3))]
    if settings.embedding_provider == "disabled":
        return lexical[:bounded_limit]
    batch = await embedding_gateway_from_settings(settings).embed([query[: settings.embedding_max_chunk_length]])
    if not batch.vectors:
        return lexical[:bounded_limit]
    semantic = semantic_candidates(db, user_id, batch.vectors[0], limit=min(50, bounded_limit * 3), include_archived=include_archived)
    lexical_scores = {item.chunk_id: item.lexical_score or 0.0 for item in lexical}
    semantic_scores = {chunk.id: score for score, _embedding, chunk, _note in semantic}
    by_chunk = {item.chunk_id: item for item in lexical}
    for score, _embedding, chunk, note in semantic:
        if chunk.id not in by_chunk:
            by_chunk[chunk.id] = _result(chunk, note, score, lexical_score=None, semantic_score=score, mode="hybrid")
    max_lexical = max(lexical_scores.values(), default=1.0) or 1.0
    combined: list[RetrievalResult] = []
    for chunk_id, item in by_chunk.items():
        lexical_score = lexical_scores.get(chunk_id)
        semantic_score = semantic_scores.get(chunk_id)
        normalized_lexical = (lexical_score / max_lexical) if lexical_score is not None else 0.0
        normalized_semantic = ((semantic_score + 1.0) / 2.0) if semantic_score is not None else 0.0
        item.lexical_score = lexical_score
        item.semantic_score = semantic_score
        item.score = (0.45 * normalized_lexical) + (0.55 * normalized_semantic)
        item.retrieval_mode = "hybrid"
        combined.append(item)
    combined.sort(key=lambda item: item.score, reverse=True)
    return combined[:bounded_limit]
