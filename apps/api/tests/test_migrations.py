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
    assert {"users", "roles", "permissions", "sessions", "audit_events", "conversations", "messages", "model_runs", "tool_calls"}.issubset(inspect(engine).get_table_names())

    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]

    command.upgrade(config, "head")
    assert "users" in inspect(engine).get_table_names()
    engine.dispose()
