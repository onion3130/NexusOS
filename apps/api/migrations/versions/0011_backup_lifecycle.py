"""backup retention lifecycle

Revision ID: 0011_backup_lifecycle
Revises: 0010_restore
Create Date: 2026-08-04

Adds ``backup_records.pruned_at`` so retention cleanup can mark pruned
artifacts while preserving audit history. The records themselves are never
hard-deleted; pruning sets ``status='deleted'`` and ``pruned_at``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_backup_lifecycle"
down_revision: str | None = "0010_restore"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("backup_records", sa.Column("pruned_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_backup_records_pruned_at"), "backup_records", ["pruned_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_backup_records_pruned_at"), table_name="backup_records")
    op.drop_column("backup_records", "pruned_at")
