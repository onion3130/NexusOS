"""approved-root external source synchronization

Revision ID: 0019_source_sync
Revises: 0018_external_sources
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_source_sync"
down_revision: Union[str, None] = "0018_external_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_sync_configs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("root_key", sa.String(64), nullable=False),
        sa.Column("relative_path", sa.String(512), nullable=False),
        sa.Column("file_id", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("interval_seconds", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(96), nullable=True),
        sa.Column("last_observed_size", sa.Integer(), nullable=True),
        sa.Column("last_observed_mtime_ns", sa.Integer(), nullable=True),
        sa.Column("last_observed_sha256", sa.String(64), nullable=True),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", name="uq_source_sync_configs_source"),
        sa.UniqueConstraint("user_id", "root_key", "relative_path", name="uq_source_sync_configs_file"),
    )
    for name, columns in (
        ("source_id", ["source_id"]),
        ("user_id", ["user_id"]),
        ("enabled_next_check", ["enabled", "next_check_at"]),
    ):
        op.create_index(f"ix_source_sync_configs_{name}", "source_sync_configs", columns)


def downgrade() -> None:
    for name in (
        "ix_source_sync_configs_enabled_next_check",
        "ix_source_sync_configs_user_id",
        "ix_source_sync_configs_source_id",
    ):
        op.drop_index(name, table_name="source_sync_configs")
    op.drop_table("source_sync_configs")
