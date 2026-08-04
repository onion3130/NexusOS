"""Alembic migration tests for the NexusOS schema history."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

API_ROOT = Path(__file__).resolve().parents[1]


def _config(database_url: str) -> Config:
    """Build an Alembic config pointed at a temporary test database."""
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_schema_upgrade_downgrade_upgrade(tmp_path) -> None:
    """The full migration history is reversible and recreatable."""
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    config = _config(database_url)

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert {"users", "roles", "permissions", "sessions", "audit_events", "conversations", "messages", "model_runs", "tool_calls", "task_categories", "tags", "task_series", "tasks", "task_tags", "reminders", "notifications", "jobs", "notes", "note_tags", "note_search_documents", "note_chunks", "notes_fts"}.issubset(inspect(engine).get_table_names())
    columns = {column["name"] for column in inspect(engine).get_columns("backup_records")}
    assert {"encryption_status", "encrypted_relative_path", "encrypted_size_bytes", "encrypted_sha256", "replication_status", "replicated_at", "replication_error_code"}.issubset(columns)

    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]

    command.upgrade(config, "head")
    assert "users" in inspect(engine).get_table_names()
    engine.dispose()
