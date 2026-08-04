"""Typed contracts for the optional embedding boundary."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EmbeddingBatch(BaseModel):
    """A bounded provider response containing normalized vectors."""

    vectors: list[list[float]] = Field(max_length=32)
    provider: str = Field(min_length=1, max_length=64)
    model: str | None = Field(default=None, max_length=128)


class EmbeddingStatus(BaseModel):
    """Safe aggregate embedding availability for the current user."""

    enabled: bool
    provider: str
    model: str | None
    dimensions: int | None
    pending: int
    ready: int
    stale: int
    failed: int


class EmbeddingError(Exception):
    """Base class for bounded embedding failures."""

    code = "embedding_unavailable"


class EmbeddingDisabledError(EmbeddingError):
    """Raised when embeddings are intentionally disabled."""

    code = "embeddings_disabled"


class EmbeddingProviderError(EmbeddingError):
    """Raised when a provider response is invalid or unavailable."""

    code = "embedding_provider_unavailable"
