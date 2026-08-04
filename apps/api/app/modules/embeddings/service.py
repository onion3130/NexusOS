"""Persistence and bounded similarity helpers for note chunk embeddings."""

from __future__ import annotations

import asyncio
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.core.config import Settings
from app.db.base import utc_now
from app.db.models import Note, NoteChunk, NoteChunkEmbedding
from app.modules.embeddings.gateway import embedding_gateway_from_settings
from app.modules.embeddings.schemas import EmbeddingError, EmbeddingStatus

MAX_RETRIES = 3


def _provider_model(settings: Settings) -> tuple[str, str] | None:
    if settings.embedding_provider == "disabled" or not settings.embedding_model:
        return None
    return settings.embedding_provider, settings.embedding_model


def ensure_pending_embeddings(db: OrmSession, settings: Settings, *, limit: int = 200) -> int:
    """Create or invalidate embedding rows for current note chunks."""
    provider_model = _provider_model(settings)
    if provider_model is None:
        return 0
    provider, model = provider_model
    chunks = db.scalars(select(NoteChunk).join(Note, Note.id == NoteChunk.note_id).where(Note.deleted_at.is_(None)).order_by(NoteChunk.updated_at.desc()).limit(max(1, min(limit, 500)))).all()
    created = 0
    for chunk in chunks:
        row = db.scalar(select(NoteChunkEmbedding).where(NoteChunkEmbedding.chunk_id == chunk.id, NoteChunkEmbedding.provider == provider, NoteChunkEmbedding.model == model))
        if row is None:
            db.add(NoteChunkEmbedding(chunk_id=chunk.id, user_id=chunk.user_id, provider=provider, model=model, dimensions=0, vector_json="[]", content_hash=chunk.content_hash, source_version=chunk.source_version, status="pending", attempts=0, available_at=utc_now()))
            created += 1
        elif row.content_hash != chunk.content_hash or row.source_version != chunk.source_version:
            row.content_hash = chunk.content_hash
            row.source_version = chunk.source_version
            row.status = "stale"
            row.available_at = utc_now()
            row.last_error_code = None
    # Keep only the active provider/model rows. Old vectors are derived data
    # and are removed transactionally after a configuration change.
    db.query(NoteChunkEmbedding).filter(NoteChunkEmbedding.provider != provider).delete(synchronize_session=False)
    db.query(NoteChunkEmbedding).filter(NoteChunkEmbedding.model != model).delete(synchronize_session=False)
    if created or chunks:
        db.commit()
    return created


def _claim_rows(db: OrmSession, settings: Settings, batch_size: int) -> list[NoteChunkEmbedding]:
    provider_model = _provider_model(settings)
    if provider_model is None:
        return []
    provider, model = provider_model
    now = datetime.now(UTC)
    rows = db.scalars(select(NoteChunkEmbedding).where(NoteChunkEmbedding.provider == provider, NoteChunkEmbedding.model == model, NoteChunkEmbedding.status.in_(["pending", "stale", "processing"]), NoteChunkEmbedding.available_at <= now, (NoteChunkEmbedding.locked_until.is_(None) | (NoteChunkEmbedding.locked_until <= now))).order_by(NoteChunkEmbedding.updated_at).limit(max(1, min(batch_size, settings.embedding_batch_size)))).all()
    claimed: list[NoteChunkEmbedding] = []
    for row in rows:
        row.status = "processing"
        row.locked_until = now + timedelta(seconds=settings.embedding_timeout_seconds + 15)
        row.attempts += 1
        claimed.append(row)
    db.commit()
    return claimed


def process_embeddings(db: OrmSession, settings: Settings, *, batch_size: int = 8) -> int:
    """Claim and process one bounded embedding batch."""
    if _provider_model(settings) is None:
        return 0
    ensure_pending_embeddings(db, settings, limit=max(batch_size * 4, 32))
    rows = _claim_rows(db, settings, batch_size)
    if not rows:
        return 0
    chunks = {chunk.id: chunk for chunk in db.scalars(select(NoteChunk).where(NoteChunk.id.in_([row.chunk_id for row in rows]))).all()}
    valid_rows: list[NoteChunkEmbedding] = []
    texts: list[str] = []
    for row in rows:
        chunk = chunks.get(row.chunk_id)
        if chunk is None or len(chunk.content) > settings.embedding_max_chunk_length:
            row.status = "failed"
            row.last_error_code = "embedding_chunk_invalid"
            row.locked_until = None
            continue
        valid_rows.append(row)
        texts.append(chunk.content[: settings.embedding_max_chunk_length])
    if not valid_rows:
        db.commit()
        return 0
    try:
        batch = asyncio.run(embedding_gateway_from_settings(settings).embed(texts))
        if len(batch.vectors) != len(valid_rows):
            raise EmbeddingError("embedding count mismatch")
        for row, vector in zip(valid_rows, batch.vectors, strict=True):
            if not vector or len(vector) > settings.embedding_max_dimensions:
                raise EmbeddingError("embedding dimensions invalid")
            row.vector_json = json.dumps(vector, separators=(",", ":"))
            row.dimensions = len(vector)
            row.provider = batch.provider
            row.model = batch.model or settings.embedding_model or "unknown"
            row.status = "ready"
            row.last_error_code = None
            row.locked_until = None
            row.updated_at = utc_now()
        db.commit()
        return len(valid_rows)
    except Exception as exc:
        for row in valid_rows:
            row.status = "failed" if row.attempts >= MAX_RETRIES else "pending"
            row.last_error_code = getattr(exc, "code", "embedding_provider_unavailable")[:96]
            row.locked_until = None
            row.available_at = datetime.now(UTC) + timedelta(seconds=min(300, 2 ** row.attempts))
        db.commit()
        return 0


def embed_query_sync(settings: Settings, query: str) -> list[float] | None:
    """Embed one query from synchronous service/tool code without blocking its event loop."""
    if _provider_model(settings) is None:
        return None

    async def run() -> list[float]:
        batch = await embedding_gateway_from_settings(settings).embed([query[: settings.embedding_max_chunk_length]])
        return batch.vectors[0] if batch.vectors else []

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run())
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(run())).result()


def _decode(vector_json: str) -> list[float]:
    """Decode and validate one bounded serialized vector."""
    value = json.loads(vector_json)
    if not isinstance(value, list) or not value or len(value) > 4096 or not all(isinstance(item, (int, float)) and math.isfinite(float(item)) for item in value):
        raise ValueError("invalid vector")
    return [float(item) for item in value]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return bounded cosine similarity for equal-dimensional vectors."""
    if len(left) != len(right) or not left:
        return -1.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return -1.0
    return dot / (left_norm * right_norm)


def semantic_candidates(db: OrmSession, user_id: str, query_vector: list[float], *, limit: int = 20, include_archived: bool = False) -> list[tuple[float, NoteChunkEmbedding, NoteChunk, Note]]:
    """Rank owned ready embeddings in a bounded Python pass."""
    statement = select(NoteChunkEmbedding, NoteChunk, Note).join(NoteChunk, NoteChunk.id == NoteChunkEmbedding.chunk_id).join(Note, Note.id == NoteChunk.note_id).where(NoteChunkEmbedding.user_id == user_id, NoteChunkEmbedding.status == "ready", Note.user_id == user_id, Note.deleted_at.is_(None)).order_by(NoteChunkEmbedding.updated_at.desc()).limit(500)
    if not include_archived:
        statement = statement.where(Note.status == "active")
    rows = db.execute(statement).all()
    ranked: list[tuple[float, NoteChunkEmbedding, NoteChunk, Note]] = []
    for embedding, chunk, note in rows:
        try:
            score = cosine_similarity(query_vector, _decode(embedding.vector_json))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if score >= -1:
            ranked.append((score, embedding, chunk, note))
    ranked.sort(key=lambda item: (-item[0], -item[3].updated_at.timestamp()))
    return ranked[: max(1, min(limit, 50))]


def embedding_status(db: OrmSession, user_id: str, settings: Settings) -> EmbeddingStatus:
    """Return aggregate status without exposing vectors or provider secrets."""
    provider_model = _provider_model(settings)
    provider, model = provider_model or ("disabled", None)
    counts = {status: int(db.scalar(select(func.count(NoteChunkEmbedding.id)).where(NoteChunkEmbedding.user_id == user_id, NoteChunkEmbedding.provider == provider, NoteChunkEmbedding.model == model, NoteChunkEmbedding.status == status)) or 0) for status in ("pending", "ready", "stale", "failed")}
    dimensions = db.scalar(select(NoteChunkEmbedding.dimensions).where(NoteChunkEmbedding.user_id == user_id, NoteChunkEmbedding.provider == provider, NoteChunkEmbedding.model == model, NoteChunkEmbedding.status == "ready").limit(1))
    return EmbeddingStatus(enabled=provider_model is not None, provider=provider, model=model, dimensions=dimensions, **counts)
