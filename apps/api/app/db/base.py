"""SQLAlchemy declarative primitives for NexusOS persistence."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all NexusOS database models."""


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for persisted events."""
    return datetime.now(UTC)
