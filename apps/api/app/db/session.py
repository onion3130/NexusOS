"""Database engine and session lifecycle for NexusOS."""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect, text

CURRENT_MIGRATION_HEAD = "0006_v1_hardening"
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create the configured synchronous SQLAlchemy engine once per process."""
    settings = get_settings()
    if settings.db_type != "sqlite":
        raise RuntimeError("NexusOS Milestone 2 supports DB_TYPE=sqlite only")

    database_url = settings.database_url
    if database_url.startswith("sqlite:///"):
        database_path = database_url.removeprefix("sqlite:///")
        if database_path and database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False, "timeout": 5},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record) -> None:
        """Enable SQLite safety/performance pragmas for every connection."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[OrmSession]:
    """Return the process-wide database session factory."""
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Generator[OrmSession, None, None]:
    """Yield one request-scoped database session and always close it."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def reset_database_caches() -> None:
    """Clear engine/session caches for tests or controlled process reconfiguration."""
    get_session_factory.cache_clear()
    get_engine.cache_clear()


def database_status(settings: Settings) -> tuple[bool, str | None]:
    """Check connectivity and whether the identity migration has been applied."""
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            tables = inspect(connection).get_table_names()
            revision = connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar() if "alembic_version" in tables else None
            fts_ready = connection.execute(text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'notes_fts' LIMIT 1")).scalar() if revision == CURRENT_MIGRATION_HEAD else 1
        if "alembic_version" not in tables or "users" not in tables or revision != CURRENT_MIGRATION_HEAD:
            return False, "migration_required"
        if not fts_ready:
            return False, "search_unavailable"
        return True, None
    except (SQLAlchemyError, OSError):
        return False, "database_unavailable"
