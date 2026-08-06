"""Alembic migration tests for the NexusOS schema history."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

API_ROOT = Path(__file__).resolve().parents[1]


def _config(database_url: str) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_legacy_v1_database_upgrades_and_reupgrades_current_head(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'legacy.db'}"
    config = _config(database_url)
    command.upgrade(config, "0006_v1_hardening")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO roles (id, key, description) VALUES (:id, 'owner', 'Owner role')"), {"id": "owner-role-for-migration-test"})
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0020_source_expansion"
        permissions = {row[0] for row in connection.execute(text("SELECT key FROM permissions WHERE key IN ('calendar.read', 'finance.read', 'media.read', 'plugins.read', 'notes.semantic', 'sources.read')"))}
        assert permissions == {"calendar.read", "finance.read", "media.read", "plugins.read", "notes.semantic", "sources.read"}
    command.downgrade(config, "0011_backup_lifecycle")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0020_source_expansion"
    engine.dispose()


def test_schema_upgrade_downgrade_upgrade(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    config = _config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert {"users", "roles", "permissions", "sessions", "audit_events", "conversations", "messages", "model_runs", "tool_calls", "task_categories", "tags", "task_series", "tasks", "task_tags", "reminders", "notifications", "notification_channel_deliveries", "jobs", "notes", "note_tags", "note_search_documents", "note_chunks", "notes_fts", "calendar_categories", "calendar_events", "calendar_event_reminders", "finance_accounts", "finance_categories", "finance_transactions", "media_items", "plugins", "plugin_runs", "assistant_source_references", "sources", "source_versions", "source_chunks", "source_sync_configs"}.issubset(inspect(engine).get_table_names())
    columns = {column["name"] for column in inspect(engine).get_columns("backup_records")}
    assert {"encryption_status", "encrypted_relative_path", "encrypted_size_bytes", "encrypted_sha256", "replication_status", "replicated_at", "replication_error_code", "restored_at", "pruned_at"}.issubset(columns)
    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    command.upgrade(config, "head")
    assert {"sources", "source_sync_configs"}.issubset(inspect(engine).get_table_names())
    columns = {column["name"] for column in inspect(engine).get_columns("sources")}
    assert "source_url" in columns
    engine.dispose()
