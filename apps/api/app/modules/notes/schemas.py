"""Typed schemas for notes, lexical search, and retrieval results."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

NoteStatus = Literal["active", "archived"]


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("timestamps must include a timezone offset")
    return value.astimezone(UTC)


class NoteCreate(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=100_000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    status: NoteStatus = "active"

    @field_validator("title", "content")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        normalized = [value.strip()[:64] for value in values if value.strip()]
        if len(set(value.casefold() for value in normalized)) != len(normalized):
            raise ValueError("tags must be unique")
        return normalized


class NoteUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, min_length=1, max_length=160)
    content: str | None = Field(default=None, min_length=1, max_length=100_000)
    tags: list[str] | None = Field(default=None, max_length=20)
    status: NoteStatus | None = None

    @field_validator("title", "content")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("tags")
    @classmethod
    def normalize_optional_tags(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = [value.strip()[:64] for value in values if value.strip()]
        if len(set(value.casefold() for value in normalized)) != len(normalized):
            raise ValueError("tags must be unique")
        return normalized


class NoteResponse(BaseModel):
    id: str
    title: str
    content: str
    status: NoteStatus
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    content_version: int
    tags: list[str]


class NoteListResponse(BaseModel):
    items: list[NoteResponse]
    next_cursor: str | None = None


class SearchResult(BaseModel):
    source_type: Literal["note"]
    source_id: str
    chunk_id: str | None
    title: str
    excerpt: str
    score: float
    updated_at: datetime
    source_version: int
    tags: list[str]


class SearchResponse(BaseModel):
    items: list[SearchResult]
    next_cursor: str | None = None


class RetrievalChunkResponse(BaseModel):
    id: str
    note_id: str
    chunk_index: int
    content: str
    content_hash: str
    start_offset: int
    end_offset: int
    source_version: int
    created_at: datetime
    updated_at: datetime


class NoteChunksResponse(BaseModel):
    items: list[RetrievalChunkResponse]


class RetrievalResult(BaseModel):
    source_type: Literal["note"]
    source_id: str
    chunk_id: str
    title: str
    excerpt: str
    score: float
    lexical_score: float | None = None
    semantic_score: float | None = None
    retrieval_mode: Literal["lexical", "semantic", "hybrid"] = "lexical"
    source_version: int
    updated_at: datetime
    metadata: dict[str, object] = Field(default_factory=dict)
